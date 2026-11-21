package organic;

import com.google.gson.stream.JsonReader;
import com.google.gson.stream.MalformedJsonException;
import java.io.IOException;
import static org.intheloop.controls.Grid.*;

public final class Cases {
    public static void main(String[] args) throws IOException {
        for (int code = 0; code < 13; code++) {
            String input = OverflowNumber.text(code);
            JsonReader r = OverflowNumber.reader(input);
            String token;
            String lexeme;
            try {
                token = r.peek().name();
                try {
                    lexeme = r.nextString();
                } catch (MalformedJsonException e) {
                    lexeme = "nextString:" + e.getClass().getSimpleName();
                }
            } catch (MalformedJsonException e) {
                token = lexeme = "peek:" + e.getClass().getSimpleName();
            }
            row(code, fields("text", input), fields("token", token, "lexeme", lexeme),
                fields("token", OverflowNumber.token(code), "lexeme", OverflowNumber.lexeme(code)));
        }
    }
}
