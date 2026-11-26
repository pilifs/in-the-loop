import java.util.*;
import javax.servlet.http.*;
import org.springframework.mock.web.MockHttpSession;

public class PublicCaller {
    static class Listener implements HttpSessionBindingListener {
        final String tag;
        final MockHttpSession session;
        final List<String> log;
        final boolean equalValues;
        Listener(String tag, MockHttpSession session, List<String> log, boolean equalValues) {
            this.tag=tag; this.session=session; this.log=log; this.equalValues=equalValues;
        }
        @Override public boolean equals(Object o) { return this==o || equalValues && o instanceof Listener l && l.equalValues; }
        @Override public int hashCode() { return equalValues ? 1 : System.identityHashCode(this); }
        void record(String phase, HttpSessionBindingEvent e) {
            if (e.getSession() != session || !"k".equals(e.getName())) throw new AssertionError("wrong event owner");
            log.add(phase + tag + ":" + ((Listener)e.getValue()).tag);
        }
        public void valueBound(HttpSessionBindingEvent e) { record("+",e); }
        public void valueUnbound(HttpSessionBindingEvent e) { record("-",e); }
    }
    public static String observe(String[] args) {
        var session = new MockHttpSession();
        var log = new ArrayList<String>();
        boolean equal=args[0].equals("equal");
        var a = new Listener("A",session,log,equal); var b = new Listener("B",session,log,equal);
        session.setAttribute("k",a);
        if (args[0].equals("remove")) session.removeAttribute("k");
        else {
            if (args[0].equals("equal")) session.setAttribute("k",a);
            session.setAttribute("k",b);
        }
        Object stored = session.getAttribute("k");
        return String.join(",",log) + " stored=" + (stored == a ? "A" : stored == b ? "B" : String.valueOf(stored));
    }
}
