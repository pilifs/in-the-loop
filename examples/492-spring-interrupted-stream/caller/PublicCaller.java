import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.reactivestreams.*;
import org.springframework.core.io.buffer.*;

public class PublicCaller {
    static class Source implements Publisher<DataBuffer> {
        final String bytes;
        final CountDownLatch demand = new CountDownLatch(1);
        final AtomicBoolean cancelled = new AtomicBoolean();
        Subscriber<? super DataBuffer> subscriber;
        Source(String bytes) { this.bytes=bytes; }
        public void subscribe(Subscriber<? super DataBuffer> s) {
            subscriber = s;
            s.onSubscribe(new Subscription() {
                boolean sent;
                public void request(long n) {
                    if (!sent) {
                        sent=true;
                        if (!bytes.isEmpty()) s.onNext(DefaultDataBufferFactory.sharedInstance.wrap(bytes.getBytes(StandardCharsets.ISO_8859_1)));
                        if (bytes.equals("ÿ")) s.onComplete();
                    }
                    demand.countDown();
                }
                public void cancel() { cancelled.set(true); }
            });
        }
    }
    public static String observe(String[] args) throws Exception {
        boolean partial = args[0].equals("partial");
        var source = new Source(partial ? "ABC" : args[0].equals("normal") ? "ÿ" : "");
        try (var in = DataBufferUtils.subscriberInputStream(source,1)) {
            if (args[0].equals("normal")) return in.read() + "," + in.read();
            var started = new CountDownLatch(1);
            var result = new AtomicReference<String>();
            Thread reader = new Thread(() -> {
                started.countDown();
                String prefix = "";
                try {
                    if (partial) {
                        Thread.currentThread().interrupt();
                        byte[] dst = new byte[7]; Arrays.fill(dst,(byte)'.');
                        int n = in.read(dst,1,5);
                        prefix = n + ":" + new String(dst,StandardCharsets.US_ASCII) + " ";
                    }
                    result.set(prefix + "read=" + in.read());
                } catch (IOException ex) {
                    result.set(prefix + ex.getClass().getSimpleName() + " flag=" + Thread.currentThread().isInterrupted()
                            + (partial ? "" : " cancelled=" + source.cancelled.get()));
                } finally { Thread.interrupted(); }
            });
            reader.setDaemon(true);
            reader.start();
            if (!started.await(3,TimeUnit.SECONDS) || !source.demand.await(3,TimeUnit.SECONDS)) throw new AssertionError("no reader");
            if (!partial) reader.interrupt();
            reader.join(750);
            if (!reader.isAlive()) return result.get();
            source.subscriber.onComplete();
            reader.join(3000);
            if (reader.isAlive()) throw new AssertionError("still waiting after completion");
            return "waiting for upstream";
        }
    }
}
