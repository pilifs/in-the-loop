/** Run one original Worker constructor or monitor caller on a JVM with a known parent-thread binding. */
public final class WorkerStartup {
    private static final int BEFORE = 41;

    static final class Key extends InheritableThreadLocal<Object> {
        final Thread parent = Thread.currentThread();
        final Object value;
        final RuntimeException failure = new IllegalStateException("child value");
        final boolean reject;
        int calls;

        Key(Object value, boolean reject) { this.value = value; this.reject = reject; }

        @Override protected Object childValue(Object inherited) {
            if (++calls != 1 || inherited != value || Thread.currentThread() != parent
                    || MonitorIdentity.shared != BEFORE) throw new AssertionError("wrong callback state");
            boolean worker = false, copy = false;
            for (StackTraceElement frame : parent.getStackTrace()) {
                worker |= frame.getClassName().equals("MonitorIdentity$Worker") && frame.getMethodName().equals("<init>");
                copy |= frame.getClassName().equals("java.lang.ThreadLocal$ThreadLocalMap") && frame.getMethodName().equals("<init>");
            }
            if (!worker || !copy) throw new AssertionError("callback outside the original constructor");
            if (reject) throw failure;
            return new Object();
        }
    }

    public static void main(String[] args) throws InterruptedException {
        String entry = args[0], binding = args[1];
        boolean reject = binding.equals("throw");
        Key key = new Key(binding.equals("null") ? null : new Object(), reject);
        if (!binding.equals("absent")) key.set(key.value);
        if (binding.equals("removed")) key.remove();
        MonitorIdentity.shared = BEFORE;
        String result;
        try {
            switch (entry) {
            case "constructor":
                if (new MonitorIdentity.Worker().getState() != Thread.State.NEW) throw new AssertionError("worker state");
                result = "NEW";
                break;
            case "matched": result = Boolean.toString(MonitorIdentity.matched()); break;
            case "mixed": result = Boolean.toString(MonitorIdentity.mixed()); break;
            case "synchronizedMethod": result = Boolean.toString(MonitorIdentity.synchronizedMethod()); break;
            default: throw new IllegalArgumentException(entry);
            }
            if (reject) throw new AssertionError("constructor swallowed childValue failure");
            if (!entry.equals("constructor") && !entry.equals("mixed") && !result.equals("true")) {
                throw new AssertionError("class monitor failed to protect the read");
            }
        } catch (RuntimeException thrown) {
            if (!reject || thrown != key.failure) throw thrown;
            result = "original exception";
        }
        int expectedCalls = binding.equals("absent") || binding.equals("removed") ? 0 : 1;
        int finalField = reject || entry.equals("constructor") ? BEFORE : 6;
        if (key.calls != expectedCalls || MonitorIdentity.shared != finalField
                || (expectedCalls != 0 && key.get() != key.value)) throw new AssertionError("parent or worker state");
        key.remove();
        System.out.println(result + "\t" + key.calls + "\t" + MonitorIdentity.shared);
    }
}
