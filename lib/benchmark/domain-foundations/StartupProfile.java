package foundation;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.nio.ByteBuffer;
import java.util.StringJoiner;

/** Fresh-process observations from unchanged application classes, with optional JVMTI field events. */
public final class StartupProfile {
    static native void mark(int phase);
    static boolean recording;
    static boolean failConstruction;
    static void phase(int n) { if (recording) mark(n); }
    static void line(String key, Object value) { System.out.print(key + "\t" + value + "\n"); }

    static String failure(Throwable error) {
        Throwable cause = error;
        while (cause instanceof InvocationTargetException && cause.getCause() != null) cause = cause.getCause();
        StringJoiner chain = new StringJoiner(">");
        while (cause != null) {
            chain.add(cause.getClass().getName());
            cause = cause.getCause();
        }
        return chain.toString();
    }

    static String units(String value) {
        StringJoiner s = new StringJoiner(",");
        for (int i = 0; i < value.length(); i++) s.add(Integer.toString(value.charAt(i)));
        return s.toString();
    }

    static void roots() throws Exception {
        String[] names = {"org.apache.avro.Schema", "org.apache.hadoop.io.BytesWritable",
            "org.apache.hadoop.mapred.JobConf", "org.apache.hadoop.security.Credentials"};
        for (int i = 0; i < names.length; i++) {
            phase(i + 1);
            Class.forName(names[i]);
            line("initialized", names[i]);
        }
    }

    static void grid(String className, String[] methods, int count) throws Exception {
        Class<?> adapter = Class.forName(className, false, StartupProfile.class.getClassLoader());
        for (int i = 0; i < methods.length; i++) {
            phase(i + 1);
            Method entry = adapter.getMethod(methods[i], int.class);
            StringJoiner values = new StringJoiner(",");
            for (int code = 0; code < count; code++) values.add(String.valueOf(entry.invoke(null, code)));
            line(methods[i], values);
        }
    }

    static void schema() throws Exception {
        Object converter = Class.forName("org.apache.avro.hadoop.io.AvroDatumConverterFactory$BytesWritableConverter")
            .getConstructor().newInstance();
        phase(2);
        Method get = converter.getClass().getMethod("getWriterSchema");
        Object saved = get.invoke(converter);
        line("type", Class.forName("org.apache.avro.Schema").getMethod("getType").invoke(saved));
        line("same", get.invoke(converter) == saved);
    }

    static void reducers(boolean overlay) throws Exception {
        Class<?> cls = Class.forName("org.apache.hadoop.mapred.JobConf");
        Object job = cls.getConstructor(boolean.class).newInstance(false);
        if (overlay) cls.getMethod("set", String.class, String.class).invoke(job, "mapreduce.job.reduces", "invalid");
        phase(2);
        line("reducers", cls.getMethod("getNumReduceTasks").invoke(job));
    }

    static void separator() throws Exception {
        Class<?> cls = Class.forName("com.github.javaparser.utils.LineSeparator");
        Object system = cls.getField("SYSTEM").get(null);
        line("separatorUnits", units((String)cls.getMethod("asRawString").invoke(system)));
    }

    static final class CheckedInitializer {
        static final int value = initialize();
        static int initialize() {
            if (failConstruction) throw new IllegalStateException("controlled initializer");
            return 1;
        }
    }

    public static void main(String[] args) {
        recording = args[0].equals("record");
        String action = args[1];
        if (args[2].equals("absent")) System.clearProperty("line.separator");
        failConstruction = args[2].equals("throws");
        for (int attempt = 0; attempt < (args[2].equals("absent") || failConstruction ? 2 : 1); attempt++) {
            phase(1);
            try {
                switch (action) {
                    case "roots" -> roots();
                    case "direct" -> grid("organic.WritableBuffer", new String[]{"directLimit"}, 21);
                    case "factory" -> grid("organic.WritableBuffer", new String[]{"bounds", "prefix", "rejected"}, 21);
                    case "schema" -> schema();
                    case "reducers" -> reducers(args[2].equals("overlay"));
                    case "node" -> grid("organic.TreeOrder", new String[]{"postorder", "preorder", "terminal"}, 2);
                    case "separator" -> separator();
                    case "initializer-control" -> {
                        int unused = CheckedInitializer.value;
                        line("remaining", ByteBuffer.wrap(new byte[]{7}, 0, 1).remaining());
                    }
                    default -> throw new IllegalArgumentException(action);
                }
            } catch (Throwable thrown) {
                line("exception", failure(thrown));
            } finally {
                phase(0);
            }
        }
    }
}
