package campaign;

import com.fasterxml.jackson.core.async.ByteArrayFeeder;
import com.fasterxml.jackson.core.json.async.NonBlockingJsonParser;
import java.io.IOException;
import java.net.URL;
import java.net.URLClassLoader;
import java.nio.file.Path;
import java.util.Arrays;

public final class ReadyTrace {
    static int closing(int code) throws IOException {
        return checkedOffset(ReadyTokens.trace(code & 31, code >> 5));
    }

    /** Return the closing token's byte offset only if every other frozen observation agrees. */
    static int checkedOffset(long[] trace) {
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
        long[] control = {3, 1, 1, 9, 2, 5, 4, 5, 6, 3, 1};
        for (int field = 0; field < control.length; field++) {
            if (field == 7) continue;
            long[] wrong = control.clone();
            wrong[field]++;
            if (checkedOffset(wrong) != -1) throw new AssertionError("accepted changed trace field " + field);
        }
        for (long offset : new long[]{-1, 5, 6, 7, 8, 0x100000005L}) {
            long[] changed = control.clone();
            changed[7] = offset;
            int expected = offset >= 5 && offset <= 8 ? (int) offset : -1;
            if (checkedOffset(changed) != expected) throw new AssertionError("incorrect closing offset " + offset);
        }
        URL[] classpath = new URL[args.length];
        for (int i = 0; i < args.length; i++) classpath[i] = Path.of(args[i]).toUri().toURL();
        for (int code = 0; code < 128; code++) {
            try (var fresh = new URLClassLoader(classpath, ClassLoader.getPlatformClassLoader());
                 var comparison = new URLClassLoader(classpath, ClassLoader.getPlatformClassLoader())) {
                var entry = fresh.loadClass("campaign.ReadyTrace").getMethod("physical", int.class);
                long[] trace = (long[]) entry.invoke(null, code);
                var dispatch = comparison.loadClass("campaign.WindowSchedules").getMethod("closing", int.class);
                if ((int) dispatch.invoke(null, code) != trace[7]) throw new AssertionError("native observer " + code);
                System.out.println(code + "\t" + Arrays.toString(trace));
            }
        }
    }
}
