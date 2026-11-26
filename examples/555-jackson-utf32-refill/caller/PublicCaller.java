import com.fasterxml.jackson.core.*;

import java.nio.charset.*;
import java.util.*;

public class PublicCaller {
    static String parse(String doc, String encoding) throws Exception {
        try (var p = new JsonFactory().createParser(doc.getBytes(Charset.forName(encoding)))) {
            if (p.nextToken() != JsonToken.START_ARRAY || p.nextToken() != JsonToken.VALUE_STRING)
                throw new AssertionError("opening tokens");
            String text = p.getText();
            if (p.nextToken() != JsonToken.END_ARRAY || p.nextToken() != null)
                throw new AssertionError("end tokens");
            return text;
        }
    }

    public static String observe(String[] a) throws Exception {
        boolean control = a[0].equals("control"), challenge = a[0].equals("challenge");
        int tested = 0;
        List<String> wrong = new ArrayList<>();
        for (int n = 3995; n <= 4001; n++) {
            StringBuilder prefix = new StringBuilder();
            for (int i = 0; i < n; i++) prefix.append((char) ('a' + i % 26));
            String value = prefix + (control ? "QR" : "\ud83d\ude00\ud800\udc00");
            for (String enc : List.of("UTF-32BE", "UTF-32LE"))
                for (int shift = 0; shift <= (challenge ? 1 : 0); shift++) {
                    String doc = " ".repeat(shift) + "[\"" + value + "\"]";
                    String actual = parse(doc, enc);
                    tested++;
                    String reference = challenge ? parse(doc, "UTF-8") : value;
                    if (!actual.equals(value)
                            || !actual.equals(reference)
                            || actual.codePointCount(0, actual.length()) != n + 2)
                        wrong.add(
                                enc
                                        + "@"
                                        + n
                                        + "+"
                                        + shift
                                        + ":"
                                        + actual.substring(Math.min(n, actual.length()))
                                                .codePoints()
                                                .mapToObj(Integer::toHexString)
                                                .toList());
                }
        }
        return "tested=" + tested + ",exact=" + (tested - wrong.size()) + ",wrong=" + wrong;
    }
}
