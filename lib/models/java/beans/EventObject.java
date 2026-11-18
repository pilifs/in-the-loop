package java.util;

/**
 * The model of {@code java.util.EventObject}, run with the model of {@code java.beans.PropertyChangeEvent} beside it
 * and only for a check that asks for that one ({@code --model java.beans.PropertyChangeEvent}): the source, as the
 * JDK's keeps it.
 *
 * <p>Kept, each as the JDK's does it: the constructor, with its {@code IllegalArgumentException("null source")} for
 * a null source; {@code getSource()}. Left out, the JDK call it names: {@code toString()}. Of every other JDK class
 * below it (the AWT's and Swing's events, {@code IndexedPropertyChangeEvent}) the constructor is the JDK's, a JDK
 * call.
 */
public class EventObject implements java.io.Serializable {
    private static final long serialVersionUID = 5516075349620653480L;

    protected transient Object source;

    public EventObject(Object source) {
        if (source == null) {
            throw new IllegalArgumentException("null source");
        }
        this.source = source;
    }

    public Object getSource() {
        return source;
    }
}
