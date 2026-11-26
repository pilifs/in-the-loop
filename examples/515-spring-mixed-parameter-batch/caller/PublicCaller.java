import org.springframework.jdbc.core.namedparam.*;
import org.springframework.jdbc.datasource.*;
import org.springframework.transaction.support.TransactionTemplate;

import java.sql.*;
import java.util.*;

import javax.sql.DataSource;

public class PublicCaller {
    public static class Bean {
        public int getId() {
            return 2;
        }

        public String getName() {
            return "bean";
        }
    }

    static String run(String scenario, boolean varargs) throws Exception {
        DataSource db =
                new DriverManagerDataSource(
                        "jdbc:h2:mem:batch" + varargs + ";DB_CLOSE_DELAY=-1", "sa", "");
        try (Connection connection = db.getConnection();
                Statement s = connection.createStatement()) {
            s.execute("create table batch_names(id integer primary key, name varchar(40))");
        }
        var source = new MapSqlParameterSource().addValue("id", 3).addValue("name", "source");
        List<Object> input = new ArrayList<>(List.of(Map.of("id", 1, "name", "map"), new Bean()));
        if (!scenario.equals("ordinary")) input.add(source);
        SqlParameterSource[] batch =
                varargs
                        ? SqlParameterSourceUtils.createBatch(input.toArray())
                        : SqlParameterSourceUtils.createBatch(input);
        if (scenario.equals("source")) {
            var third = batch[2];
            String value;
            try {
                value = String.valueOf(third.getValue("name"));
            } catch (IllegalArgumentException e) {
                value = e.getClass().getSimpleName();
            }
            return (source == third) + ":" + third.hasValue("name") + ":" + value;
        }
        if (scenario.equals("mutate")) source.addValue("name", "revised");
        var template = new NamedParameterJdbcTemplate(db);
        new TransactionTemplate(new DataSourceTransactionManager(db))
                .execute(
                        status ->
                                template.batchUpdate(
                                        "insert into batch_names values (:id,:name)", batch));
        var rows = new ArrayList<String>();
        try (var connection = db.getConnection();
                var s = connection.createStatement();
                var r = s.executeQuery("select id,name from batch_names order by id")) {
            while (r.next()) rows.add(r.getInt(1) + "=" + r.getString(2));
        }
        return scenario.equals("ordinary")
                ? Arrays.stream(batch).map(v -> v.getValue("name")).toList() + ":" + rows
                : rows.toString();
    }

    public static String observe(String[] args) throws Exception {
        String first = run(args[0], false);
        return args[0].equals("ordinary") ? first + " / " + run(args[0], true) : first;
    }
}
