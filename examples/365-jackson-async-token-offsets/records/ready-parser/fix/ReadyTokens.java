package campaign;

import java.io.IOException;
import com.fasterxml.jackson.core.JsonFactory;
import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.core.JsonToken;
import com.fasterxml.jackson.core.async.ByteArrayFeeder;
import com.fasterxml.jackson.core.json.async.NonBlockingUtf8JsonParserBase;

public final class ReadyTokens {
    // Three triples, the total number of tokens, and the terminal state (1 for final EOF).
    static long[] trace(int mask, int padding) throws IOException {
        byte[] document = {'[', 't', 'r', 'u', 'e', ']'};
        long[] result = new long[11];
        try (JsonParser parser = ReadyParser.INSTANCE) {
            ByteArrayFeeder feeder = (ByteArrayFeeder) parser.getNonBlockingInputFeeder();
            int start = 0;
            for (int end = 1; end <= document.length; end++) {
                boolean last = end == document.length;
                if (!last && (mask & (1 << (end - 1))) == 0) continue;
                int width = end - start;
                byte[] bytes = new byte[padding + width + 1];
                for (int i = 0; i < padding; i++) bytes[i] = '!';
                bytes[bytes.length - 1] = '?';
                System.arraycopy(document, start, bytes, padding, width);
                feeder.feedInput(bytes, padding, padding + width);
                if (last) feeder.endOfInput();
                while (true) {
                    JsonToken token = ((NonBlockingUtf8JsonParserBase) parser).nextToken();
                    if (token == null) {
                        result[10] = last ? 1 : -1;
                        return result;
                    }
                    if (token == JsonToken.NOT_AVAILABLE) break;
                    int n = (int) result[9]++;
                    if (n >= 3) return result;
                    result[3 * n] = token.id();
                    result[3 * n + 1] = parser.currentTokenLocation().getByteOffset();
                    result[3 * n + 2] = parser.currentLocation().getByteOffset();
                }
                start = end;
            }
        }
        return result;
    }

    static boolean correctOffsets(long[] t) {
        return t[0] == 3 && t[1] == 1 && t[2] == 1 && t[3] == 9 && t[4] == 2 && t[5] == 5
            && t[6] == 4 && t[7] == 5 && t[8] == 6 && t[9] == 3 && t[10] == 1;
    }
    public static int offsets(int code) throws IOException {
        return correctOffsets(trace(code & 31, code >> 5)) ? 1 : 0;
    }
    public static int tokens(int code) throws IOException {
        long[] t = trace(code & 31, code >> 5);
        return t[0] == 3 && t[3] == 9 && t[6] == 4 && t[9] == 3 && t[10] == 1 ? 1 : 0;
    }
}
