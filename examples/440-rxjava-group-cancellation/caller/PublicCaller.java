import java.util.ArrayList;
import java.util.List;
import io.reactivex.rxjava3.core.*;
import io.reactivex.rxjava3.flowables.GroupedFlowable;
import org.reactivestreams.Subscription;

public class PublicCaller {
    static class Recorder<T> implements FlowableSubscriber<T> {
        final long demand;
        final List<T> values = new ArrayList<>();
        Subscription sub;
        boolean completed;
        String error = "-";
        Recorder(long demand) { this.demand=demand; }
        public void onSubscribe(Subscription s) { sub=s; if (demand>0) s.request(demand); }
        public void onNext(T item) { values.add(item); }
        public void onError(Throwable e) { error=e.getClass().getName(); }
        public void onComplete() { completed=true; }
        String state() { return values+"/"+completed+"/"+error; }
    }
    public static String observe(String[] args) {
        boolean control = args[0].equals("control"), limited=args[0].equals("limited");
        var slow = new Recorder<Integer>(control ? Long.MAX_VALUE : 0);
        var live = new Recorder<Integer>(limited ? 1 : Long.MAX_VALUE);
        var outer = new Recorder<GroupedFlowable<Integer,Integer>>(Long.MAX_VALUE) {
            public void onNext(GroupedFlowable<Integer,Integer> group) {
                group.subscribe(group.getKey()==0 ? slow : live);
            }
        };
        Flowable.range(1,8).groupBy(i -> i<=3 ? 0 : 1, i -> i, false, 4).subscribe(outer);
        String first = live.state();
        if (!control) slow.sub.cancel();
        String cancelled = live.state();
        if (limited) live.sub.request(4);
        return "initial="+first+" afterCancel="+cancelled+" final="+live.state()
                +" firstGroup="+slow.state()+" outer="+outer.completed+"/"+outer.error;
    }
}
