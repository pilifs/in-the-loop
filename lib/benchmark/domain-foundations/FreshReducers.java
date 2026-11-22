package foundation;
import org.apache.hadoop.mapred.JobConf;

public final class FreshReducers {
    private static final String KEY = "mapreduce.job.reduces";
    public static boolean fresh() {
        JobConf conf = new JobConf(false);
        return conf.getNumReduceTasks() == 1 && conf.getNumReduceTasks() == 1;
    }
    public static boolean isolated() {
        JobConf first = new JobConf(false);
        JobConf second = new JobConf(false);
        first.set(KEY, " 0x10 ");
        return first.getNumReduceTasks() == 16 && second.getNumReduceTasks() == 1;
    }
    public static boolean malformed() {
        JobConf conf = new JobConf(false);
        conf.set(KEY, "invalid");
        try { conf.getNumReduceTasks(); return false; }
        catch (NumberFormatException expected) { return true; }
    }
    public static boolean resource() {
        JobConf conf = new JobConf(false);
        conf.addResource("reducers-explicit.xml");
        return conf.getNumReduceTasks() == 7;
    }
    public static void main(String[] args) {
        boolean ok = switch (args[0]) {
            case "fresh" -> fresh();
            case "isolated" -> isolated();
            case "malformed" -> malformed();
            case "resource" -> resource();
            default -> throw new IllegalArgumentException(args[0]);
        };
        if (!ok) throw new AssertionError(args[0]);
    }
}
