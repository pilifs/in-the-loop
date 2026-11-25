import java.nio.charset.StandardCharsets;
import java.sql.*;
import java.time.Instant;
import java.util.Date;
import java.util.Properties;
import java.util.Set;
import java.util.TimeZone;
import org.quartz.*;
import org.quartz.impl.StdSchedulerFactory;
import org.quartz.utils.ConnectionProvider;

public class PublicCaller {
    public static class Connections implements ConnectionProvider {
        static boolean postgres;
        static String schema;
        static Connection open() throws SQLException {
            if (!postgres) return DriverManager.getConnection("jdbc:derby:memory:schedules;create=true");
            return DriverManager.getConnection("jdbc:postgresql://127.0.0.1:" +
                    System.getenv("PUBLIC_COMPARISON_PG_PORT") + "/postgres", "postgres",
                    System.getenv("PUBLIC_COMPARISON_PG_PASSWORD"));
        }
        public Connection getConnection() throws SQLException {
            var conn = open();
            if (postgres) conn.setSchema(schema);
            return conn;
        }
        public void initialize() {}
        public void shutdown() {}
    }
    public static class Noop implements Job { public void execute(JobExecutionContext context) {} }

    static final Date START = Date.from(Instant.parse("2099-01-01T00:00:00Z"));
    static Trigger trigger(JobDetail job, String group, boolean cron, boolean initial) {
        var t = TriggerBuilder.newTrigger().withIdentity("t", group).forJob(job).startAt(START);
        if (cron) return t.withSchedule(CronScheduleBuilder.cronSchedule("0 0 12 * * ?")
                .inTimeZone(TimeZone.getTimeZone("UTC"))).build();
        var s = SimpleScheduleBuilder.simpleSchedule().withIntervalInMilliseconds(initial ? 400000 : 60000);
        return t.withSchedule(initial ? s.repeatForever() : s.withRepeatCount(3)).build();
    }
    static String read(Scheduler scheduler, String group) {
        try {
            Trigger t = scheduler.getTrigger(new TriggerKey("t",group));
            String kind = t instanceof CronTrigger c ? c.getCronExpression()+"/"+c.getTimeZone().getID()
                    : ((SimpleTrigger)t).getRepeatCount()+"/"+((SimpleTrigger)t).getRepeatInterval();
            return t.getKey()+"/"+t.getJobKey()+"/"+kind;
        } catch (SchedulerException ex) { return ex.getClass().getName(); }
    }
    static String stored(ConnectionProvider db, String group) throws SQLException {
        String where = " WHERE SCHED_NAME=? AND TRIGGER_NAME=? AND TRIGGER_GROUP=?";
        try (var c = db.getConnection()) {
            var values = new java.util.ArrayList<String>();
            for (var sql : new String[]{"SELECT TRIGGER_TYPE FROM QRTZ_TRIGGERS",
                    "SELECT COUNT(*) FROM QRTZ_SIMPLE_TRIGGERS", "SELECT COUNT(*) FROM QRTZ_CRON_TRIGGERS"}) {
                try (var q=c.prepareStatement(sql+where)) {
                    q.setString(1,"probe"); q.setString(2,"t"); q.setString(3,group);
                    try (var rs=q.executeQuery()) { while (rs.next()) values.add(rs.getString(1)); }
                }
            }
            return String.join(",", values);
        }
    }
    static String pair(Scheduler sch, ConnectionProvider db) throws SQLException {
        return read(sch,"g")+" "+stored(db,"g")+" | "+read(sch,"other")+" "+stored(db,"other");
    }
    public static String observe(String[] args) throws Exception {
        Connections.postgres = System.getenv("PUBLIC_COMPARISON_PG_PORT") != null;
        var db = new Connections();
        if (Connections.postgres) {
            Connections.schema = "q" + java.util.UUID.randomUUID().toString().replace("-","");
            try (var c=Connections.open(); var st=c.createStatement()) { st.execute("CREATE SCHEMA "+Connections.schema); }
        }
        String dialect = Connections.postgres ? "postgres" : "derby";
        String resource="/org/quartz/impl/jdbcjobstore/tables_"+dialect+".sql";
        try (var in=Scheduler.class.getResourceAsStream(resource); var c=db.getConnection(); var st=c.createStatement()) {
            String ddl=new String(in.readAllBytes(), StandardCharsets.UTF_8).replaceAll("(?m)--.*$", "");
            for (String item : ddl.split(";")) {
                String sql=item.trim();
                String keyword = sql.split("\\s+", 2)[0].toUpperCase(java.util.Locale.ROOT);
                if (Set.of("CREATE", "ALTER", "INSERT").contains(keyword)) st.execute(sql);
            }
        }
        var props = new Properties();
        props.setProperty("org.quartz.scheduler.instanceName","probe");
        props.setProperty("org.quartz.threadPool.threadCount","1");
        props.setProperty("org.quartz.jobStore.class","org.quartz.impl.jdbcjobstore.JobStoreTX");
        props.setProperty("org.quartz.jobStore.driverDelegateClass","org.quartz.impl.jdbcjobstore."
                +(Connections.postgres ? "PostgreSQLDelegate" : "StdJDBCDelegate"));
        props.setProperty("org.quartz.jobStore.dataSource","fixture");
        props.setProperty("org.quartz.dataSource.fixture.connectionProvider.class",Connections.class.getName());
        var sch=new StdSchedulerFactory(props).getScheduler();
        try {
            var main=JobBuilder.newJob(Noop.class).withIdentity("job","g").build();
            sch.scheduleJob(main,trigger(main,"g",false,true));
            String initial=read(sch,"g");
            boolean sequence=args[0].equals("two");
            if (sequence) {
                var other=JobBuilder.newJob(Noop.class).withIdentity("job","other").build();
                sch.scheduleJob(other,trigger(other,"other",false,true));
            }
            sch.scheduleJob(main,Set.of(trigger(main,"g",!args[0].equals("simple"),false)),true);
            if (!sequence) return initial+" -> "+read(sch,"g");
            String first=pair(sch,db);
            sch.scheduleJob(main,Set.of(trigger(main,"g",false,false)),true);
            return initial+" -> "+first+" -> "+pair(sch,db);
        } finally { sch.shutdown(); }
    }
}
