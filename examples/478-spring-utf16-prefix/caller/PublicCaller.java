import java.nio.CharBuffer;
import java.nio.charset.*;
import java.util.stream.Collectors;
import org.springframework.util.StringUtils;

public class PublicCaller {
    static String units(String text) {
        String suffix = " (truncated)...";
        boolean truncated = text.endsWith(suffix);
        String prefix = truncated ? text.substring(0, text.length() - suffix.length()) : text;
        return prefix.chars().mapToObj(c -> String.format("%04x", c)).collect(Collectors.joining(" "))
                + " |suffix=" + truncated;
    }

    public static String observe(String[] args) throws CharacterCodingException {
        String text = "a😀b";
        if (args[0].equals("cut")) return units(StringUtils.truncate(text, 2));
        if (args[0].equals("whole")) return units(StringUtils.truncate(text, 3)) + " / " + units(StringUtils.truncate(text, 4));
        var result = StringUtils.truncate(new StringBuilder("a😀😀b"), 4);
        var encoder = StandardCharsets.UTF_8.newEncoder().onMalformedInput(CodingErrorAction.REPORT);
        try {
            return StandardCharsets.UTF_8.decode(encoder.encode(CharBuffer.wrap(result))).toString();
        } catch (MalformedInputException e) {
            return e.getClass().getSimpleName();
        }
    }
}
