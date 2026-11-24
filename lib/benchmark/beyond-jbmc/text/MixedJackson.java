import java.util.Arrays;

public final class MixedJackson {
    public static void main(String[] argv) throws Exception {
        String[] words = {"-0.", "+7.", "99.", ".", "7.e1", "", "x", "0", "\u0661"};
        for (String word : words) {
            if (before.JacksonNumbers.looks(word) != JacksonNumbers.looks(word))
                throw new AssertionError(word);
            for (int type = 0; type < 4; ++type) {
                if (!Arrays.equals(before.DatabindAPI.read(word, type), DatabindAPI.read(word, type)))
                    throw new AssertionError(word + " type " + type);
            }
        }
        System.out.println("9 predicates and 36 typed observations agree");
    }
}
