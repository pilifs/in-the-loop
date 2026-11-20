package chunks;
import java.nio.charset.StandardCharsets;

public final class DecodeCases {
    public static void main(String[] args) throws Exception {
        String[] alphabet = {"A", "\u00e9", "\ud83d\ude00"};
        int code = 0;
        for (int len = 0, words = 1; len <= 3; len++, words *= 3) {
            for (int ordinal = 0; ordinal < words; ordinal++) {
                int value = ordinal;
                String[] symbols = new String[len];
                for (int i = len - 1; i >= 0; i--, value /= 3) symbols[i] = alphabet[value % 3];
                String word = String.join("", symbols);
                byte[] bytes = word.getBytes(StandardCharsets.UTF_8);
                int total = 1 << Math.max(0, bytes.length - 1);
                for (int mask = 0; mask < total; mask++) {
                    Inputs.Result actual = Decoder.decode(bytes, mask);
                    StringBuilder units = new StringBuilder();
                    for (int i = 0; i < actual.text().length(); i++) {
                        String hex = Integer.toHexString(actual.text().charAt(i));
                        units.append("0000", 0, 4 - hex.length()).append(hex);
                    }
                    System.out.printf("{\"id\":%d,\"units\":\"%s\",\"eof\":%b}%n", code++, units, actual.eof());
                }
            }
        }
        if (code != 5578) throw new AssertionError(code);
    }
}
