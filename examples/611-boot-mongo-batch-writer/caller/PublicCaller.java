import java.util.concurrent.atomic.AtomicReference;
import com.mongodb.client.*;
import org.bson.Document;
import org.springframework.batch.core.job.parameters.JobParametersBuilder;
import org.springframework.batch.core.repository.JobRepository;
import org.springframework.batch.infrastructure.item.ExecutionContext;
import org.springframework.boot.autoconfigure.AutoConfigurations;
import org.springframework.boot.batch.autoconfigure.BatchTransactionManager;
import org.springframework.boot.batch.mongodb.autoconfigure.BatchDataMongoAutoConfiguration;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.context.annotation.*;
import org.springframework.data.mongodb.*;
import org.springframework.data.mongodb.core.*;
import org.springframework.transaction.*;

public class PublicCaller {
    static class Recording implements PlatformTransactionManager {
        final MongoTransactionManager delegate;
        int starts, commits;
        Recording(MongoDatabaseFactory db) { delegate = new MongoTransactionManager(db); }
        public TransactionStatus getTransaction(TransactionDefinition def) {
            TransactionStatus tx = delegate.getTransaction(def);
            if (tx.isNewTransaction()) starts++;
            return tx;
        }
        public void commit(TransactionStatus status) {
            boolean newTx = status.isNewTransaction();
            delegate.commit(status);
            if (newTx) commits++;
        }
        public void rollback(TransactionStatus status) { delegate.rollback(status); }
    }
    static class CountedMongo extends MongoTransactionManager {
        int acquisitions;
        CountedMongo(MongoDatabaseFactory db) { super(db); }
        @Override protected void doBegin(Object tx,TransactionDefinition def) { super.doBegin(tx,def); acquisitions++; }
    }
    @Configuration(proxyBeanMethods=false) static class Sole {
        @Bean Recording recording(MongoDatabaseFactory db) { return new Recording(db); }
    }
    @Configuration(proxyBeanMethods=false) static class Ordinary {
        @Bean MongoTransactionManager mongo(MongoDatabaseFactory db) { return new MongoTransactionManager(db); }
    }
    @Configuration(proxyBeanMethods=false) static class Qualified {
        @Bean @Primary CountedMongo primaryManager(MongoDatabaseFactory db) { return new CountedMongo(db); }
        @Bean @BatchTransactionManager Recording chosen(MongoDatabaseFactory db) { return new Recording(db); }
    }
    public static String observe(String[] args) throws Exception {
        int port = ComposeProject.freeTcpPort();
        String service = "    image: mongo:5.0.17@sha256:ee514514754ffdb13597a894bdae90fdabbe4c0926bf96b40a84d1233782bcc1\n"
                + "    command: ['mongod','--replSet','fixture','--bind_ip_all','--port','" + port + "','--oplogSize','64']\n"
                + "    ports:\n      - '127.0.0.1:" + port + ":" + port + "/tcp'\n"
                + "    healthcheck:\n      test: ['CMD','mongo','--quiet','--port','" + port + "','--eval','db.adminCommand({ping:1}).ok']\n"
                + "      interval: 1s\n      timeout: 3s\n      retries: 15\n";
        try (var project = new ComposeProject(service)) {
            project.command("exec","-T","fixture","mongo","--quiet","--port",Integer.toString(port),"--eval",
                    "rs.initiate({_id:'fixture',members:[{_id:0,host:'127.0.0.1:" + port + "'}]})");
            String uri = "mongodb://127.0.0.1:" + port + "/?replicaSet=fixture&serverSelectionTimeoutMS=12000";
            try (var client = MongoClients.create(uri)) {
                var db = new SimpleMongoClientDatabaseFactory(client, "batch_fixture");
                var output = new AtomicReference<String>();
                boolean control = args[0].equals("control"), challenge=args[0].equals("challenge");
                new ApplicationContextRunner().withConfiguration(AutoConfigurations.of(BatchDataMongoAutoConfiguration.class))
                        .withBean(MongoDatabaseFactory.class, () -> db)
                        .withBean(MongoOperations.class, () -> new MongoTemplate(db))
                        .withPropertyValues("spring.batch.data.mongodb.schema.initialize=true")
                        .withUserConfiguration(control ? Ordinary.class : challenge ? Qualified.class : Sole.class).run(ctx -> {
                    var repo = ctx.getBean(JobRepository.class);
                    var recording = ctx.getBeanProvider(Recording.class).getIfAvailable();
                    var primary = ctx.getBeanProvider(CountedMongo.class).getIfAvailable();
                    if (recording != null) { recording.starts = 0; recording.commits = 0; }
                    if (primary != null) primary.acquisitions = 0;
                    var params = new JobParametersBuilder().addString("fixture",args[0]).toJobParameters();
                    var instance = repo.createJobInstance("probe",params);
                    var execution = repo.createJobExecution(instance,params,new ExecutionContext());
                    String chosen = control ? "" : (recording.starts > 0) + ":" + (recording.commits > 0) + ":";
                    if (challenge) chosen += (primary.acquisitions > 0) + ":";
                    var read = repo.getJobExecution(execution.getId());
                    output.set(chosen + (read != null && read.getId() == execution.getId()
                            && read.getJobInstance().getId() == instance.getId() && "probe".equals(read.getJobInstance().getJobName())));
                });
                return output.get();
            }
        }
    }
}
