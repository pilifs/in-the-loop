import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Iterator;
import java.util.List;
import org.apache.commons.collections4.iterators.IteratorChain;

/** The input, depth and timed operations of IteratorChainTest.testChainingPerformsWell. */
public class Depth {
    public static void main(String[] args) {
        List<String> first = new ArrayList<>(Arrays.asList("One","Two","Three"));
        List<String> second = new ArrayList<>(Collections.singletonList("Four"));
        List<String> third = new ArrayList<>(Arrays.asList("Five","Six"));
        IteratorChain<String> initial = new IteratorChain<>();
        initial.addIterator(first.iterator()); initial.addIterator(second.iterator()); initial.addIterator(third.iterator());
        Iterator<String> iter = initial;
        for (int i=0; i<150; i++) {
            IteratorChain<String> next = new IteratorChain<>();
            next.addIterator(iter);
            iter = next;
        }
        List<String> observed = new ArrayList<>();
        long start = System.nanoTime();
        for (String expected : Arrays.asList("One","Two","Three","Four","Five","Six")) {
            String actual = iter.next();
            if (!expected.equals(actual)) throw new AssertionError(actual);
            observed.add(actual);
            if (!"Four".equals(actual)) iter.remove();
        }
        if (iter.hasNext() || !first.isEmpty() || second.size()!=1 || !third.isEmpty())
            throw new AssertionError("final backing lists or exhaustion");
        long nanos = System.nanoTime()-start;
        System.out.println(nanos + "\t" + observed + "\t" + first + "/" + second + "/" + third);
    }
}
