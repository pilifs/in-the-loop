import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import ch.qos.logback.classic.Logger;
import ch.qos.logback.classic.spi.ILoggingEvent;
import ch.qos.logback.core.read.ListAppender;
import org.junit.jupiter.api.*;
import org.junit.platform.launcher.*;
import org.junit.platform.launcher.core.*;
import org.junit.platform.launcher.listeners.SummaryGeneratingListener;
import org.junit.platform.engine.discovery.DiscoverySelectors;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.context.logging.LoggingApplicationListener;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.ApplicationContext;
import org.springframework.context.annotation.Configuration;
import org.springframework.test.context.TestPropertySource;

public class PublicCaller {
    @Configuration(proxyBeanMethods=false) static class Config {}
    static final List<ApplicationContext> contexts = new ArrayList<>();
    static final ListAppender<ILoggingEvent> sink = new ListAppender<>();
    static void emit(ApplicationContext ctx, String id) {
        contexts.add(ctx);
        Logger logger = (Logger) LoggerFactory.getLogger("fixture.jul");
        if (!logger.isAttached(sink)) { sink.setContext(logger.getLoggerContext()); sink.start(); logger.addAppender(sink); }
        java.util.logging.Logger.getLogger("fixture.jul").severe("jul-" + id);
        logger.info("direct-" + id);
    }
    @SpringBootTest(classes=Config.class,webEnvironment=SpringBootTest.WebEnvironment.NONE)
    @TestClassOrder(ClassOrderer.ClassName.class)
    static class Sequence {
        @Nested @TestPropertySource(properties="context=one") class A { @Test void emitA(@Autowired ApplicationContext c) { emit(c,"A"); } }
        @Nested @TestPropertySource(properties="context=two") class B { @Test void emitB(@Autowired ApplicationContext c) { emit(c,"B"); } }
        @Nested @TestPropertySource(properties="context=one") class C { @Test void emitC(@Autowired ApplicationContext c) { emit(c,"C"); } }
        @Nested @Tag("fourth") @TestPropertySource(properties="context=two") class D { @Test void emitD(@Autowired ApplicationContext c) { emit(c,"D"); } }
    }
    public static void main(String[] args) {
        if (!LoggingApplicationListener.class.getProtectionDomain().getCodeSource().getLocation().toString().equals(args[1]))
            throw new AssertionError("different child Boot logging artifact");
        var b = LauncherDiscoveryRequestBuilder.request().selectors(DiscoverySelectors.selectClass(Sequence.class));
        boolean more = args[0].equals("challenge");
        if (!more) b.filters(TagFilter.excludeTags("fourth"));
        var listener = new SummaryGeneratingListener();
        LauncherFactory.create().execute(b.build(), listener);
        int n = more ? 4 : 3;
        if (listener.getSummary().getTestsSucceededCount() != n || contexts.size() != n) throw new AssertionError("sequence failed");
        boolean reused = contexts.get(0) == contexts.get(2) && contexts.get(0) != contexts.get(1)
                && (!more || contexts.get(1) == contexts.get(3));
        var counts = new ArrayList<String>();
        for (String id : List.of("A","B","C","D").subList(0,n)) {
            long jul = sink.list.stream().filter(e -> ("jul-"+id).equals(e.getFormattedMessage())).count();
            long direct = sink.list.stream().filter(e -> ("direct-"+id).equals(e.getFormattedMessage())).count();
            counts.add(jul + "/" + direct);
        }
        System.out.println("OBS reused:" + reused + ";" + String.join(",",counts));
    }
    public static String observe(String[] args) throws Exception {
        var cmd = new ArrayList<String>();
        cmd.add(Path.of(System.getProperty("java.home"), "bin", "java").toString());
        cmd.add("-Xmx160m");
        if (args[0].equals("control")) cmd.add("-Dspring.test.context.cache.pause=never");
        cmd.addAll(List.of("-cp",System.getProperty("java.class.path"),PublicCaller.class.getName(), args[0],
                LoggingApplicationListener.class.getProtectionDomain().getCodeSource().getLocation().toString()));
        Path log = Files.createTempFile("jul-reuse", ".log");
        var child = new ProcessBuilder(cmd).redirectErrorStream(true).redirectOutput(log.toFile()).start();
        try {
            if (!child.waitFor(20, TimeUnit.SECONDS) || child.exitValue() != 0) throw new IllegalStateException("child test sequence failed");
            var rows = Files.readAllLines(log).stream().filter(s -> s.startsWith("OBS ")).toList();
            if (rows.size() != 1) throw new AssertionError("expected one result");
            return rows.getFirst().substring(4);
        } finally { if (child.isAlive()) child.destroyForcibly(); }
    }
}
