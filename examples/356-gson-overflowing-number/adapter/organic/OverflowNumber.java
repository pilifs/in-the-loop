package organic;

import com.google.gson.Strictness;
import com.google.gson.stream.JsonReader;
import com.google.gson.stream.JsonToken;
import com.google.gson.stream.MalformedJsonException;
import java.io.IOException;
import java.io.StringReader;

public final class OverflowNumber {
    static String text(int code) {
        if (code < 10) return "18446744073709551616" + (char) ('0' + code);
        if (code == 10) return "10";
        return code == 11 ? "00" : "01";
    }

    static JsonReader reader(String input) {
        JsonReader reader = new JsonReader(new StringReader(input));
        reader.setStrictness(Strictness.STRICT);
        return reader;
    }

    public static int token(int code) throws IOException {
        JsonReader r = reader(text(code));
        try {
            JsonToken token = r.peek();
            return code <= 10 && token == JsonToken.NUMBER ? 1 : 0;
        } catch (MalformedJsonException rejected) {
            return code > 10 ? 1 : 0;
        }
    }

    public static int lexeme(int code) throws IOException {
        String input = text(code);
        JsonReader r = reader(input);
        try {
            JsonToken token = r.peek();
            if (code > 10 || token != JsonToken.NUMBER) return 0;
            return r.nextString().equals(input) ? 1 : 0;
        } catch (MalformedJsonException rejected) {
            return code > 10 ? 1 : 0;
        }
    }
}
