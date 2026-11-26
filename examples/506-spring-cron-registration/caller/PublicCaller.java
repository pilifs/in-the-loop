import java.time.*;
import java.time.format.DateTimeFormatter;
import org.springframework.scheduling.TriggerContext;
import org.springframework.scheduling.config.*;
import org.springframework.scheduling.support.CronTrigger;

public class PublicCaller {
    static final String EXPRESSION="0 0 9 * * *";
    static final ZoneId LONDON=ZoneId.of("Europe/London");
    static int calls;
    static final Runnable TASK=() -> calls++;
    static String next(ScheduledTaskRegistrar reg,Clock clock) {
        var tasks=reg.getCronTaskList();
        if(tasks.size()!=1) throw new AssertionError("task count " + tasks.size());
        int before=calls;
        tasks.get(0).getRunnable().run();
        if(calls!=before+1) throw new AssertionError("registered runnable did not invoke the supplied task");
        var context=new TriggerContext() {
            public Clock getClock(){return clock;}
            public Instant lastScheduledExecution(){return null;}
            public Instant lastActualExecution(){return null;}
            public Instant lastCompletion(){return null;}
        };
        Instant next=tasks.get(0).getTrigger().nextExecution(context);
        if(!next.atZone(ZoneOffset.UTC).toLocalDate().equals(clock.instant().atZone(ZoneOffset.UTC).toLocalDate()))
            return next.toString();
        return DateTimeFormatter.ofPattern("HH:mm'Z'").withZone(ZoneOffset.UTC).format(next);
    }
    static String form(boolean overload,Clock clock) {
        var reg=new ScheduledTaskRegistrar();
        if(overload) {
            try {reg.addCronTask(TASK,EXPRESSION,LONDON);} catch(NoSuchMethodError absent) {return "unavailable";}
        } else reg.addCronTask(new CronTask(TASK,new CronTrigger(EXPRESSION,LONDON)));
        return next(reg,clock);
    }
    public static String observe(String[] args) {
        boolean seasons=args[0].equals("seasons");
        ZoneId zone=seasons ? ZoneId.of("Asia/Tokyo") : ZoneOffset.UTC;
        var summer=Clock.fixed(Instant.parse("2025-07-15T00:00:00Z"),zone);
        var winter=Clock.fixed(Instant.parse("2025-01-15T00:00:00Z"),zone);
        if(args[0].equals("disabled")) {
            var reg=new ScheduledTaskRegistrar();reg.addCronTask(TASK,EXPRESSION);
            var original=reg.getCronTaskList().get(0);
            reg.addCronTask(TASK,ScheduledTaskRegistrar.CRON_DISABLED);
            try {reg.addCronTask(TASK,ScheduledTaskRegistrar.CRON_DISABLED,LONDON);} catch(NoSuchMethodError absent) {}
            return "count="+reg.getCronTaskList().size()+" next="+next(reg,summer)+" disabled="+(reg.getCronTaskList().get(0)==original);
        }
        String explicit=form(false,summer),overload=form(true,summer);
        if(seasons) {explicit+="/"+form(false,winter); if(!overload.equals("unavailable")) overload+="/"+form(true,winter);}
        return "explicit="+explicit+" overload="+overload;
    }
}
