package campaign;

import com.fasterxml.jackson.core.async.ByteArrayFeeder;
import com.fasterxml.jackson.core.json.async.NonBlockingJsonParser;
import java.io.IOException;
import java.net.URL;
import java.net.URLClassLoader;
import java.nio.file.Path;
import java.util.Arrays;

public final class ReadyTrace {
    /** Return the closing token's byte offset only if every other frozen observation agrees. */
    static int closing(int code) throws IOException {
        long[] trace = ReadyTokens.trace(code & 31, code >> 5);
        long closing = trace[7];
        trace[7] = 5;
        if (!ReadyTokens.correctOffsets(trace) || closing < 0 || closing > Integer.MAX_VALUE) return -1;
        return (int) closing;
    }

    public static long[] physical(int code) throws IOException {
        var parser = ReadyParser.INSTANCE;
        if (parser.getClass() != NonBlockingJsonParser.class || parser.isClosed() || parser.currentToken() != null
                || parser.currentLocation().getByteOffset() != 0
                || !((ByteArrayFeeder) parser.getNonBlockingInputFeeder()).needMoreInput())
            throw new AssertionError("factory did not supply an unused byte-array parser");
        long[] trace = ReadyTokens.trace(code & 31, code >> 5);
        if (!parser.isClosed()) throw new AssertionError("parser still open after EOF");
        return trace;
    }

    public static void main(String[] args) throws Exception {
        URL[] classpath = new URL[args.length];
        for (int i = 0; i < args.length; i++) classpath[i] = Path.of(args[i]).toUri().toURL();
        for (int code = 0; code < 128; code++) {
            try (var fresh = new URLClassLoader(classpath, ClassLoader.getPlatformClassLoader())) {
                var entry = fresh.loadClass("campaign.ReadyTrace").getMethod("physical", int.class);
                System.out.println(code + "\t" + Arrays.toString((long[]) entry.invoke(null, code)));
            }
        }
    }
}
