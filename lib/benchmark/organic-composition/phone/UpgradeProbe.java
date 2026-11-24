import com.google.i18n.phonenumbers.AsYouTypeFormatter;
import com.google.i18n.phonenumbers.PhoneNumberUtil;

public class UpgradeProbe {
    public static String observe(String[] args) {
        AsYouTypeFormatter formatter = PhoneNumberUtil.getInstance().getAsYouTypeFormatter(args[0]);
        StringBuilder trace = new StringBuilder();
        for (int pass = 0; pass < 2; pass++) {
            if (pass == 1) {
                formatter.clear();
                trace.append("|clear@").append(formatter.getRememberedPosition()).append('|');
            }
            for (int i = 0; i < args[1].length(); i++) {
                char digit = args[1].charAt(i);
                String prefix = i == 3 ? formatter.inputDigitAndRememberPosition(digit) : formatter.inputDigit(digit);
                if (i != 0) trace.append('/');
                trace.append(prefix).append('@').append(formatter.getRememberedPosition());
            }
        }
        return trace.toString();
    }

    public static boolean phone(boolean swedish) {
        return observe(swedish ? new String[]{"SE","08123456"} : new String[]{"EC","022123456"})
               .contains(swedish ? "08-12" : "02 21");
    }
}
