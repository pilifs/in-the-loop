package java.beans;

import java.util.EventObject;

/**
 * The model of {@code java.beans.PropertyChangeEvent}: its source (kept by the model of {@code java.util.EventObject},
 * {@code EventObject.java} beside this file), the property's name, its old and new values, and the propagation id, as
 * the JDK's keeps them. The own checker runs it only for a check that asks for it
 * ({@code --model java.beans.PropertyChangeEvent}, which runs the model of {@code EventObject} too); otherwise the
 * class is the JDK's, whose calls the checker does not run. Spring's bean wrapper makes one for each value it cannot
 * convert (the event a {@code TypeMismatchException} carries, example 286).
 *
 * <p>Kept, each as the JDK's does it: the constructor, with the {@code IllegalArgumentException} of
 * {@code EventObject}'s for a null source; {@code getPropertyName()}, {@code getNewValue()}, {@code getOldValue()},
 * {@code getPropagationId()} and {@code setPropagationId(Object)}, and {@code getSource()} of {@code EventObject}.
 * Each is a field read or written.
 *
 * <p>Left out, each the JDK call it names: {@code toString()} (the class's name and every field, through
 * {@code getClass()} and string concatenation of the values' own {@code toString}) and the package-private
 * {@code appendTo}. A subclass ({@code IndexedPropertyChangeEvent}) is the JDK's, its constructor a JDK call.
 */
public class PropertyChangeEvent extends EventObject {
    private static final long serialVersionUID = 7042693688939648123L;

    private String propertyName;
    private Object newValue;
    private Object oldValue;
    private Object propagationId;

    public PropertyChangeEvent(Object source, String propertyName, Object oldValue, Object newValue) {
        super(source);
        this.propertyName = propertyName;
        this.newValue = newValue;
        this.oldValue = oldValue;
    }

    public String getPropertyName() {
        return propertyName;
    }

    public Object getNewValue() {
        return newValue;
    }

    public Object getOldValue() {
        return oldValue;
    }

    public void setPropagationId(Object propagationId) {
        this.propagationId = propagationId;
    }

    public Object getPropagationId() {
        return propagationId;
    }
}
