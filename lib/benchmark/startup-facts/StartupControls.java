import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

/** A symbolic two-profile selection, plus deterministic partial and overlapping startup controls. */
public class StartupControls {
    public static int explicit(boolean asciiSelected) {
        return "é".getBytes(StandardCharsets.UTF_8).length;
    }
    public static int selected(boolean asciiSelected) {
        Charset choice = asciiSelected ? StandardCharsets.US_ASCII : StandardCharsets.UTF_8;
        return "é".getBytes(choice).length;
    }
    public static class Hold {
        static {
            try {
                Files.writeString(Path.of(System.getProperty("startup.fixture.ready")), "second root entered");
                Thread.sleep(60000);
            } catch (Exception e) { throw new ExceptionInInitializerError(e); }
        }
    }
    public static class Child {
        static int value;
        static { value = 9; }
    }
    static class Worker implements Runnable {
        public void run() { if (Child.value != 9) throw new AssertionError(); }
    }
    public static class Threaded {
        static int value;
        static {
            Thread worker = new Thread(new Worker(), "startup-control");
            worker.start();
            try { worker.join(); } catch (InterruptedException e) { throw new ExceptionInInitializerError(e); }
            value = 9;
        }
    }
    public static int threaded() { return Threaded.value; }
}
