package claims;

import java.util.Enumeration;
import java.util.NoSuchElementException;
import java.util.StringTokenizer;

public final class Tokens {
    public static boolean history(boolean supplementary) {
        String delimiter = supplementary ? "\ud83d\ude03" : ",";
        String input = "a" + delimiter + delimiter + "b:c";
        StringTokenizer tokens = new StringTokenizer(input, delimiter);
        Enumeration<Object> view = tokens;
        if (tokens.countTokens() != 2 || !view.hasMoreElements() || !view.nextElement().equals("a")) return false;
        // The cached position from hasMoreTokens must be discarded when the delimiters change.
        if (!tokens.hasMoreTokens() || !tokens.nextToken(":").equals(delimiter + delimiter + "b")) return false;
        if (!tokens.nextToken().equals("c") || view.hasMoreElements() || tokens.countTokens() != 0) return false;
        try {
            view.nextElement();
            return false;
        } catch (NoSuchElementException expected) {
            return true;
        }
    }

    public static boolean returnsDelimiters() {
        StringTokenizer tokens = new StringTokenizer("x\ud83d\ude03y", "\ud83d\ude03", true);
        return tokens.countTokens() == 3 && tokens.nextToken().equals("x")
            && tokens.nextToken().equals("\ud83d\ude03") && tokens.nextToken().equals("y") && !tokens.hasMoreTokens();
    }

    public static boolean edgeCases() {
        StringTokenizer overridden = new StringTokenizer("a") {
            @Override public String nextToken() { return "override"; }
        };
        if (!overridden.nextElement().equals("override")) return false;
        // A null delimiter is accepted at construction and fails on the first token query.
        StringTokenizer tokens = new StringTokenizer("x", null);
        try {
            tokens.hasMoreTokens();
            return false;
        } catch (NullPointerException expected) {
            return tokens.nextToken("").equals("x");
        }
    }

    public static boolean wrong(boolean comma) {
        return new StringTokenizer(comma ? ",,a," : "a,b", ",").countTokens() == 1;
    }

    public static void main(String[] args) {
        if (!history(false) || !history(true) || !returnsDelimiters() || !edgeCases() || !wrong(true) || wrong(false))
            throw new AssertionError();
    }
}
