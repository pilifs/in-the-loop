package organic;
import java.io.ByteArrayOutputStream;
import java.nio.ByteBuffer;
import org.apache.avro.io.BufferedBinaryEncoder;

/** A separate JVM for each call, with the thread's interrupt flag explicitly observed. */
public final class EncoderInterrupt {
    public static void main(String[] args) throws Exception {
        int code = Integer.parseInt(args[0]);
        ByteBuffer view = EncoderWindow.window(code);
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        BufferedBinaryEncoder encoder = EncoderWindow.encoder(out);
        if (Thread.currentThread().isInterrupted()) throw new AssertionError("unexpected initial interrupt");
        if (Boolean.parseBoolean(args[1])) Thread.currentThread().interrupt();
        String outcome = "returned";
        try { encoder.writeFixed(view); encoder.flush(); }
        catch (java.io.IOException failure) { outcome = failure.getClass().getName(); }
        System.out.println(outcome+" "+view.position()+" "+view.limit()+" "+out.size()+" "+Thread.interrupted());
    }
}
