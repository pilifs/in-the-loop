package chunks;

import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;

public final class Inputs {
    record Input(String word, byte[] bytes, int cuts) {}
    record Result(String text, boolean eof) {}

    static Input at(int code) {
        String[] alphabet = {"A", "\u00e9", "\ud83d\ude00"};
        for (int len = 0, words = 1; len <= 3; len++, words *= 3) {
            for (int ordinal = 0; ordinal < words; ordinal++) {
                String word = "";
                int digits = ordinal;
                for (int i = 0; i < len; i++, digits /= 3) word = alphabet[digits % 3] + word;
                byte[] bytes = word.getBytes(StandardCharsets.UTF_8);
                int partitions = 1 << Math.max(0, bytes.length - 1);
                if (code < partitions) return new Input(word, bytes, code);
                code -= partitions;
            }
        }
        throw new IllegalArgumentException("selector");
    }

    static Result read(InputStream input) throws IOException {
        try (InputStreamReader reader = new InputStreamReader(input, StandardCharsets.UTF_8)) {
            StringBuilder text = new StringBuilder();
            int unit;
            while ((unit = reader.read()) != -1) text.append((char) unit);
            return new Result(text.toString(), reader.read() == -1);
        }
    }

    public static int units(int code) throws IOException {
        Input in = at(code);
        return Decoder.decode(in.bytes(), in.cuts()).text().equals(in.word()) ? 1 : 0;
    }

    public static int eof(int code) throws IOException {
        Input in = at(code);
        return Decoder.decode(in.bytes(), in.cuts()).eof() ? 1 : 0;
    }
}
