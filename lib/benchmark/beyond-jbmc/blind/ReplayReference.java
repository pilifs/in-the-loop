// Compiled against the original-graph bridges and the locked ReferencePair.
public final class ReplayReference {
    public static void main(String[] args) throws Exception {
        int n = Integer.parseInt(args[0]);
        if (!ReferencePair.admitted(n)) throw new AssertionError("outside the reference domain");
        long old = before.ReferenceAPI.primary(n), current = ReferenceAPI.primary(n);
        long oldControl = before.ReferenceAPI.control(n), currentControl = ReferenceAPI.control(n);
        if (old != ReferencePair.oldExpected(n) || current != ReferencePair.newExpected(n)
                || oldControl != ReferencePair.controlExpected(n) || currentControl != ReferencePair.controlExpected(n)
                || !ReferencePair.primary(n) || !ReferencePair.control(n) || ReferencePair.inverse(n))
            throw new AssertionError("reference mismatch at " + n);
        System.out.println(n + " " + old + " " + current + " " + oldControl + " " + currentControl);
    }
}
