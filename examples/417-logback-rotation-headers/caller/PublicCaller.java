import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import ch.qos.logback.core.ContextBase;
import ch.qos.logback.core.encoder.EncoderBase;
import ch.qos.logback.core.rolling.*;
import ch.qos.logback.core.util.FileSize;

public class PublicCaller {
    static byte[] bytes(String s) { return s.getBytes(StandardCharsets.US_ASCII); }
    static String read(String f) throws Exception {
        return new String(Files.readAllBytes(Path.of(f)), StandardCharsets.US_ASCII);
    }
    public static String observe(String[] args) throws Exception {
        var context = new ContextBase();
        var app = new RollingFileAppender<String>();
        app.setContext(context);
        app.setFile("current.log");
        var encoder = new EncoderBase<String>() {
            public byte[] headerBytes() { return bytes("H"); }
            public byte[] encode(String event) { return bytes(event); }
            public byte[] footerBytes() { return bytes("F"); }
        };
        encoder.setContext(context);
        encoder.start();
        app.setEncoder(encoder);
        var roll = new FixedWindowRollingPolicy();
        roll.setContext(context);
        roll.setParent(app);
        roll.setFileNamePattern("part-%i.log");
        roll.setMinIndex(1);
        roll.setMaxIndex(3);
        roll.start();
        app.setRollingPolicy(roll);
        var trigger = new SizeBasedTriggeringPolicy<String>();
        trigger.setContext(context);
        trigger.setMaxFileSize(FileSize.valueOf("1MB"));
        trigger.start();
        app.setTriggeringPolicy(trigger);
        app.start();
        if (!app.isStarted()) throw new IllegalStateException("appender startup");
        app.doAppend("A");
        int rotations = args[0].equals("twice") ? 2 : args[0].equals("rotate") ? 1 : 0;
        for (int i = 0; i < rotations; i++) app.rollover();
        app.doAppend("B");
        app.stop();
        context.stop();
        var result = new StringJoiner("; ");
        for (int i = rotations; i > 0; i--) result.add("archive" + i + "=" + read("part-" + i + ".log"));
        return result.add("active=" + read("current.log")).toString();
    }
}
