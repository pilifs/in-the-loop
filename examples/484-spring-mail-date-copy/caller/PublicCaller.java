import java.util.Date;
import org.springframework.mail.SimpleMailMessage;

public class PublicCaller {
    static class Recording extends SimpleMailMessage {
        Date captured;
        @Override public void setSentDate(Date value) { captured = value; }
    }
    static String millis(Date d) { return d == null ? "null" : Long.toString(d.getTime()); }
    static String pair(SimpleMailMessage a, SimpleMailMessage b) {
        return millis(a.getSentDate()) + "/" + millis(b.getSentDate());
    }
    public static String observe(String[] args) {
        var target = new Recording();
        target.setSentDate(new Date(77));
        var m = args[0].equals("subclass") ? new SimpleMailMessage() {
            @Override public Date getSentDate() { return new Date(1234); }
        } : new SimpleMailMessage();
        Date input = new Date(1234);
        if (args[0].equals("mutations")) m.setSentDate(input);
        if (args[0].equals("unset")) m.setSentDate(null);
        var copy = new SimpleMailMessage(m);
        m.copyTo(target);
        if (!args[0].equals("mutations")) return pair(m,copy) + "/" + millis(target.captured);
        input.setTime(0);
        String first = pair(m,copy);
        m.getSentDate().setTime(1);
        String second = pair(m,copy);
        target.captured.setTime(2);
        return first + " " + second + " " + pair(m,copy);
    }
}
