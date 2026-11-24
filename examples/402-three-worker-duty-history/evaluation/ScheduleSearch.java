import java.util.*;

/** Discover schedules from the next actual requests; the controller never reads or writes the duty state to choose. */
public final class ScheduleSearch implements Duty.Gates {
    final boolean[] waiting=new boolean[3],done=new boolean[3];
    final String[] operation=new String[3]; final List<Integer> prefix,order=new ArrayList<>();
    final List<List<Integer>> enabled=new ArrayList<>(); final List<String> events=new ArrayList<>();
    int permitted=-1, acknowledgements, failures;
    Duty.Board root;
    ScheduleSearch(List<Integer> prefix){this.prefix=prefix;}
    void pause(){try{wait(10000);}catch(InterruptedException e){throw new IllegalStateException(e);}}
    public synchronized void before(int id,String op,Duty.Board b) {
        if(root==null)root=b;
        if(root!=b)throw new IllegalStateException("multiple duty roots");
        operation[id]=op;waiting[id]=true;notifyAll();
        while(permitted!=id)pause(); waiting[id]=false;
    }
    public synchronized void after(int id,String op,Duty.Board b,boolean decision) {
        if(b!=root || permitted!=id)throw new IllegalStateException("unpermitted action");
        events.add(id+"/"+op+"/"+decision+"/"+b.mask+"/"+b.commits);
        permitted=-1;acknowledgements++;notifyAll();
    }
    public synchronized void failed(int id){failures++;notifyAll();}
    public synchronized void done(int id){done[id]=true;notifyAll();}
    synchronized void control() {
        for(;;) {
            boolean ready=true;var choices=new ArrayList<Integer>();
            for(int i=0;i<3;i++){if(!waiting[i]&&!done[i])ready=false;if(waiting[i])choices.add(i);}
            if(!ready){pause();continue;}
            if(choices.isEmpty())return;
            int pos=order.size();int id=pos<prefix.size()?prefix.get(pos):choices.get(0);
            if(!choices.contains(id))throw new IllegalArgumentException("infeasible schedule prefix "+prefix);
            enabled.add(choices);order.add(id);permitted=id;notifyAll();
            while(acknowledgements<=pos)pause();
        }
    }
    List<Integer> successor() {
        for(int i=order.size()-1;i>=0;i--)for(int n:enabled.get(i))if(n>order.get(i)){
            var next=new ArrayList<>(order.subList(0,i));next.add(n);return next;
        }
        return null;
    }
    public static void main(String[] args) throws Exception {
        if(!Duty.Board.class.desiredAssertionStatus())throw new IllegalStateException("enable assertions");
        boolean split=args[0].equals("split"),force=Boolean.parseBoolean(args[1]);
        List<Integer> prefix=new ArrayList<>();
        if(args.length==3)for(char c:args[2].toCharArray())prefix.add(c-'0');
        do {
            var s=new ScheduleSearch(prefix);
            Thread caller=new Thread(()->{try{Duty.execute(split,force,s);}catch(InterruptedException e){throw new IllegalStateException(e);}});
            caller.start();s.control();caller.join();
            if(s.root.commits!=3||s.failures>1)throw new IllegalStateException("incomplete history");
            StringBuilder trace=new StringBuilder();s.order.forEach(trace::append);
            System.out.println(trace+" "+s.root.mask+" "+s.root.commits+" "+s.failures+" "+String.join(";",s.events));
            prefix=args.length==3?null:s.successor();
        } while(prefix!=null);
    }
}
