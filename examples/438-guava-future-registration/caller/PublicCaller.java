import java.util.concurrent.*;
import com.google.common.util.concurrent.*;

public class PublicCaller {
    static class Counted extends ForwardingListenableFuture.SimpleForwardingListenableFuture<String> {
        final SettableFuture<String> source;
        int listeners;
        boolean completeOnFirst;
        Counted(SettableFuture<String> source) { super(source); this.source=source; }
        public void addListener(Runnable listener, Executor executor) {
            listeners++;
            if (completeOnFirst && listeners == 1) source.set("X");
            super.addListener(listener, executor);
        }
    }
    public static String observe(String[] args) throws Exception {
        var a = new Counted(SettableFuture.create());
        var b = new Counted(SettableFuture.create());
        if (args[0].equals("duplicate")) {
            a.completeOnFirst = true;
            var both = Futures.allAsList(a,a);
            return "list=" + both.get(2, TimeUnit.SECONDS) + " registrations=" + a.listeners;
        }
        boolean early = args[0].equals("done");
        if (early) a.source.set("a");
        var both = Futures.allAsList(a,b);
        boolean initial = both.isDone();
        b.source.set("b");
        boolean afterB = both.isDone();
        if (!early) a.source.set("a");
        return "registrations=" + a.listeners + "/" + b.listeners + " initial=" + initial + " afterB="
                + afterB + " list=" + both.get(2, TimeUnit.SECONDS);
    }
}
