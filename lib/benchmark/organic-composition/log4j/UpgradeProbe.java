import java.util.TimeZone;
import org.apache.logging.log4j.core.appender.rolling.PatternProcessor;

public final class UpgradeProbe {
    static final long START = 1393927200000L; // 2014-03-04T10:00:00Z

    public static String observe(String[] args) {
        TimeZone original = TimeZone.getDefault();
        try {
            TimeZone.setDefault(TimeZone.getTimeZone(args[0]));
            String pattern = "logs/app-%d{yyyy-MM-dd}" + (args[1].equals("explicit") ? "{GMT-6}" : "") + ".log.gz";
            PatternProcessor processor = new PatternProcessor(pattern);
            processor.setTimeBased(args[2].equals("time-based"));
            processor.setPrevFileTime(13L);
            processor.setCurrentFileTime(17L);
            processor.updateTime();
            StringBuilder state = new StringBuilder().append(processor.getPrevFileTime()).append(',')
                    .append(processor.getCurrentFileTime());
            long first = 0;
            for (int i = 0; i < 3; ++i) {
                long now = i == 0 ? START : first + i - 2;
                processor.setCurrentFileTime(31L + i);
                long deadline = processor.getNextTime(now, 1, false);
                if (i == 0) first = deadline;
                state.append('/').append(deadline).append(',').append(processor.getNextFileTime())
                     .append(',').append(processor.getPrevFileTime()).append(',').append(processor.getCurrentFileTime());
                processor.updateTime();
                state.append(',').append(processor.getPrevFileTime()).append(',').append(processor.getCurrentFileTime());
            }
            return state.toString();
        } finally {
            TimeZone.setDefault(original);
        }
    }

    public static boolean schedule() {
        return observe(new String[]{"GMT+10:00", "explicit", "time-based"}).startsWith("13,17/");
    }
}
