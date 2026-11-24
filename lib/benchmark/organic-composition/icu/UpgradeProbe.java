import com.ibm.icu.text.BreakIterator;
import com.ibm.icu.text.RuleBasedBreakIterator;
import com.ibm.icu.util.ULocale;

public class UpgradeProbe {
    public static String observe(String[] args) {
        RuleBasedBreakIterator iter = (RuleBasedBreakIterator) BreakIterator.getWordInstance(new ULocale(args[0]));
        StringBuilder out = new StringBuilder();
        for (String text : new String[]{"xx:yy", "𐐀:𐐨", "xx:yy"}) {
            if (out.length() != 0) out.append('|');
            iter.setText(text);
            for (int at = iter.first(); at != BreakIterator.DONE; at = iter.next()) {
                if (at != 0) out.append(',');
                out.append(at).append(':').append(iter.getRuleStatus());
            }
            out.append('/');
            for (int at = iter.last(); at != BreakIterator.DONE; at = iter.previous()) {
                if (at != text.length()) out.append(',');
                out.append(at).append(':').append(iter.getRuleStatus());
            }
        }
        return out.toString();
    }

    public static boolean english(boolean posix) {
        return observe(new String[]{posix ? "en_US_POSIX" : "en_US"}).startsWith("0:0,5:200/");
    }
}
