package sn;

import java.lang.reflect.Method;

/**
 * A library's property writer: the setter is found by reflection, its name the property's with the first unit
 * upper-cased, so both "age" and "Age" write age. The tool's own checker does not run reflection: without a stand-in
 * a call of {@link #set} is a gap.
 */
public class Wrapper {

	private final Object target;

	public Wrapper(Object target) {
		this.target = target;
	}

	public Object getTarget() {
		return this.target;
	}

	public void set(String name, String value) {
		if (name.isEmpty()) {
			return;
		}
		String setter = "set" + Character.toUpperCase(name.charAt(0)) + name.substring(1);
		for (Method m : this.target.getClass().getMethods()) {
			if (m.getName().equals(setter) && m.getParameterCount() == 1) {
				Object converted = m.getParameterTypes()[0] == int.class ? (Object) Integer.parseInt(value) : value;
				try {
					m.invoke(this.target, converted);
				}
				catch (ReflectiveOperationException ex) {
					throw new IllegalStateException(ex);
				}
				return;
			}
		}
	}
}
