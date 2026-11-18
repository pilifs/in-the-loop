package claims;

import java.util.ArrayDeque;
import java.util.Deque;
import java.util.NoSuchElementException;
import java.util.Random;

/**
 * An {@code ArrayDeque} used as a stack, as Spring's {@code AbstractErrors} keeps its nested paths (example 286):
 * each method returns whether the deque does what the JDK documents, so a proof of {@code result} with
 * {@code --model java.util.ArrayDeque} is a proof that the model and the definition agree on every input of the
 * bound, and {@code main} runs the same methods on a JVM over sampled inputs, where the deque is the JDK's.
 */
public class Deques {
    static final class Item {
        final int value;

        Item(int value) {
            this.value = value;
        }
    }

    /**
     * Pushed in order, then popped {@code pops} times: each push the new top ({@code peek}) and one more element,
     * each pop the element pushed last that is left, the same object; past the last, {@code NoSuchElementException}
     * and nothing changed.
     */
    public static boolean stacked(int[] a, int pops) {
        Deque<Item> deque = new ArrayDeque<>();
        if (!deque.isEmpty() || deque.size() != 0 || deque.peek() != null) {
            return false;
        }
        int n = a.length;
        Item[] made = new Item[n];
        for (int i = 0; i < n; i++) {
            made[i] = new Item(a[i]);
            deque.push(made[i]);
            if (deque.peek() != made[i] || deque.size() != i + 1 || deque.isEmpty()) {
                return false;
            }
        }
        int left = n;
        for (int k = 0; k < pops && k < n + 1; k++) {
            Item popped;
            try {
                popped = deque.pop();
            }
            catch (NoSuchElementException e) {
                if (left != 0) {
                    return false;
                }
                return deque.isEmpty() && deque.size() == 0 && deque.peek() == null;
            }
            if (left == 0 || popped != made[left - 1]) {
                return false;
            }
            left--;
            if (deque.size() != left || deque.isEmpty() != (left == 0) || deque.peek() != (left == 0 ? null : made[left - 1])) {
                return false;
            }
        }
        return true;
    }

    /** {@code push(null)} throws {@code NullPointerException} and leaves the deque as it was. */
    public static boolean refused(int[] a) {
        Deque<Item> deque = new ArrayDeque<>();
        Item last = null;
        for (int i = 0; i < a.length; i++) {
            last = new Item(a[i]);
            deque.push(last);
        }
        try {
            deque.push(null);
            return false;
        }
        catch (NullPointerException e) {
            return deque.size() == a.length && deque.peek() == last;
        }
    }

    /** {@code clear()} empties the deque, which then takes pushes again from nothing. */
    public static boolean cleared(int[] a, boolean again) {
        Deque<Item> deque = new ArrayDeque<>();
        for (int i = 0; i < a.length; i++) {
            deque.push(new Item(a[i]));
        }
        deque.clear();
        if (!deque.isEmpty() || deque.size() != 0 || deque.peek() != null) {
            return false;
        }
        if (again) {
            Item one = new Item(1);
            deque.push(one);
            return deque.size() == 1 && deque.pop() == one && deque.isEmpty();
        }
        return true;
    }

    /** {@code offer}, which the model does not keep: the JDK call it names. */
    public static boolean offered(int x) {
        Deque<Item> deque = new ArrayDeque<>();
        return deque.offer(new Item(x)) && deque.size() == 1;
    }

    /** Runs each method over sampled inputs of up to 4 elements on this JVM; prints "ok" or the first that fails. */
    public static void main(String[] args) {
        int samples = Integer.parseInt(args[0]);
        Random random = new Random(286);
        for (int s = 0; s < samples; s++) {
            int[] a = new int[random.nextInt(5)];
            for (int i = 0; i < a.length; i++) {
                a[i] = random.nextInt();
            }
            int pops = random.nextInt(7);
            boolean again = random.nextBoolean();
            if (!stacked(a, pops) || !refused(a) || !cleared(a, again) || !offered(a.length)) {
                System.out.println("fails: " + java.util.Arrays.toString(a) + " pops " + pops + " again " + again);
                return;
            }
        }
        System.out.println("ok");
    }
}
