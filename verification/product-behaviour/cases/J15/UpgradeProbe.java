import java.lang.reflect.InvocationHandler;
import java.lang.reflect.Proxy;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Date;
import java.util.List;
import java.util.Map;
import java.util.HashMap;
import org.springframework.batch.core.*;
import org.springframework.batch.core.repository.JobRepository;
import org.springframework.batch.core.repository.dao.*;
import org.springframework.batch.core.repository.support.JobRepositoryFactoryBean;
import org.springframework.batch.core.repository.support.SimpleJobRepository;
import org.springframework.batch.item.ExecutionContext;
import org.springframework.batch.item.file.FlatFileItemReader;
import org.springframework.core.io.ClassPathResource;
import org.springframework.core.io.FileSystemResource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.jdbc.datasource.init.ResourceDatabasePopulator;

public class UpgradeProbe {
    private static final long START = 1500000000000L;

    private static FlatFileItemReader<String> reader() throws Exception {
        FlatFileItemReader<String> reader = new FlatFileItemReader<>();
        reader.setName("rows");
        reader.setResource(new FileSystemResource("rows.txt"));
        reader.setLineMapper((line, number) -> line);
        reader.afterPropertiesSet();
        return reader;
    }

    private static ExecutionContext checkpoint(int offset) throws Exception {
        ExecutionContext context = new ExecutionContext();
        FlatFileItemReader<String> reader = reader();
        reader.open(context);
        try {
            for (int i = 0; i < offset; i++)
                if (!("row-" + i).equals(reader.read())) throw new AssertionError("input row " + i);
            reader.update(context);
            context.putString("marker", "saved-" + offset);
            return context;
        } finally { reader.close(); }
    }

    private static JobRepository jdbc(DriverManagerDataSource source) throws Exception {
        JobRepositoryFactoryBean factory = new JobRepositoryFactoryBean();
        factory.setDataSource(source);
        factory.setTransactionManager(new DataSourceTransactionManager(source));
        factory.setDatabaseType("HSQL");
        factory.afterPropertiesSet();
        return factory.getObject();
    }

    private static <T> T dao(Class<T> type, InvocationHandler action) {
        return type.cast(Proxy.newProxyInstance(type.getClassLoader(), new Class<?>[]{type}, action));
    }

    private static JobRepository controlled(JobInstance job, boolean reverse, boolean later) throws Exception {
        List<JobExecution> jobs = new ArrayList<>();
        Map<Long, ExecutionContext> saved = new HashMap<>();
        for (int i = 1; i <= 2; i++) {
            JobExecution run = new JobExecution(job, (long)i, new JobParameters(), null);
            jobs.add(run);
            StepExecution step = run.createStepExecution("import");
            step.setStartTime(new Date(START + (later && i == 1 ? 1000 : 0)));
            step.setId((long)i);
            saved.put((long)i, checkpoint(i == 1 ? 2 : 5));
        }
        if (reverse) Collections.reverse(jobs);
        JobExecutionDao jobDao = dao(JobExecutionDao.class, (p, m, a) -> {
            if (m.getName().equals("findJobExecutions")) return jobs;
            throw new AssertionError(m);
        });
        StepExecutionDao stepDao = dao(StepExecutionDao.class, (p, m, a) -> {
            if (m.getName().equals("addStepExecutions")) return null;
            throw new AssertionError(m);
        });
        ExecutionContextDao contexts = dao(ExecutionContextDao.class, (p, m, a) -> {
            if (!m.getName().equals("getExecutionContext")) throw new AssertionError(m);
            return a[0] instanceof StepExecution ? saved.get(((StepExecution)a[0]).getId()) : new ExecutionContext();
        });
        return new SimpleJobRepository(dao(JobInstanceDao.class, (p, m, a) -> { throw new AssertionError(m); }),
                                       jobDao, stepDao, contexts);
    }

    public static String observe(String[] args) throws Exception {
        Files.write(Paths.get("rows.txt"), Arrays.asList("row-0","row-1","row-2","row-3","row-4","row-5","row-6"), StandardCharsets.UTF_8);
        boolean later = args[1].equals("later");
        String stepName = args[1].equals("absent") ? "missing" : "import";
        JobInstance job;
        JobRepository repository;
        DriverManagerDataSource reopened = null;
        if (args[0].equals("jdbc")) {
            String url = "jdbc:hsqldb:file:" + Paths.get("batch").toAbsolutePath();
            DriverManagerDataSource source = new DriverManagerDataSource(url, "SA", "");
            try (java.sql.Connection connection = source.getConnection()) {
                new ResourceDatabasePopulator(new ClassPathResource("org/springframework/batch/core/schema-hsqldb.sql")).populate(connection);
            }
            new JdbcTemplate(source).execute("ALTER TABLE BATCH_STEP_EXECUTION_SEQ ALTER COLUMN ID RESTART WITH 1");
            JobRepository writer = jdbc(source);
            JobParameters parameters = new JobParameters();
            job = writer.createJobInstance("inventory", parameters);
            for (int i = 1; i <= 2; i++) {
                JobExecution run = writer.createJobExecution(job, parameters, null);
                StepExecution step = run.createStepExecution("import");
                step.setStartTime(new Date(START + (later && i == 1 ? 1000 : 0)));
                step.setExecutionContext(checkpoint(i == 1 ? 2 : 5));
                writer.add(step);
                if (step.getId() != i) throw new AssertionError("persisted step id " + step.getId());
            }
            new JdbcTemplate(source).execute("SHUTDOWN");
            reopened = new DriverManagerDataSource(url, "SA", "");
            repository = jdbc(reopened);
            job = new JobInstance(job.getId(), job.getJobName());
        } else {
            job = new JobInstance(100L, "inventory");
            repository = controlled(job, args[0].equals("reverse"), later);
        }
        StepExecution selected = repository.getLastStepExecution(job, stepName);
        String result = "none";
        if (selected != null) {
            ExecutionContext context = selected.getExecutionContext();
            FlatFileItemReader<String> resumed = reader();
            resumed.open(context);
            try {
                result = selected.getId() + "/" + context.getString("marker") + "/" + context.getInt("rows.read.count")
                        + "/" + resumed.read() + "/" + resumed.read();
            } finally { resumed.close(); }
        }
        if (reopened != null) new JdbcTemplate(reopened).execute("SHUTDOWN");
        return result;
    }
}
