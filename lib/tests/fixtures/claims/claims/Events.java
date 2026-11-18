package claims;

import java.beans.PropertyChangeEvent;
import java.util.EventObject;
import java.util.Random;

/**
 * A {@code PropertyChangeEvent}, as Spring's bean wrapper makes one for a value it cannot convert (example 286): each
 * method returns whether the event does what the JDK documents, so a proof of {@code result} with
 * {@code --model java.beans.PropertyChangeEvent} is a proof that the model and the definition agree on every input of
 * the bound, and {@code main} runs the same methods on a JVM over sampled inputs, where the event is the JDK's.
 */
public class Events {
    static final class Thing {
        final int value;

        Thing(int value) {
            this.value = value;
        }
    }

    /**
     * Made with a source, a name and two values: the source, the name and each value are the very objects given, also
     * through {@code EventObject}; no propagation id until one is set; a null source is
     * {@code IllegalArgumentException}, and a null name or value is kept as null.
     */
    public static boolean made(String name, int x, boolean noSource, boolean noOld) {
        Thing source = noSource ? null : new Thing(x);
        Thing old = noOld ? null : new Thing(x + 1);
        PropertyChangeEvent e;
        try {
            e = new PropertyChangeEvent(source, name, old, name);
        }
        catch (IllegalArgumentException ex) {
            return noSource;
        }
        if (noSource) {
            return false;
        }
        EventObject o = e;
        if (o.getSource() != source || e.getSource() != source || e.getPropertyName() != name || e.getOldValue() != old || e.getNewValue() != name || e.getPropagationId() != null) {
            return false;
        }
        Thing id = new Thing(x);
        e.setPropagationId(id);
        return e.getPropagationId() == id && e.getSource() == source && e.getPropertyName() == name;
    }

    /** {@code toString}, which the model does not keep: the JDK call it names. */
    public static boolean described(int x) {
        return new PropertyChangeEvent(new Thing(x), "p", null, null).toString() != null;
    }

    /** Runs each method over sampled inputs on this JVM; prints "ok" or the first that fails. */
    public static void main(String[] args) {
        int samples = Integer.parseInt(args[0]);
        Random random = new Random(286);
        String[] names = {null, "", "p", "someMap", "SomeMap", "İ", "a b"};
        for (int s = 0; s < samples; s++) {
            String name = names[random.nextInt(names.length)];
            int x = random.nextInt();
            boolean noSource = random.nextInt(4) == 0;
            boolean noOld = random.nextBoolean();
            if (!made(name, x, noSource, noOld) || !described(x)) {
                System.out.println("fails: " + name + " " + x + " " + noSource + " " + noOld);
                return;
            }
        }
        System.out.println("ok");
    }
}
