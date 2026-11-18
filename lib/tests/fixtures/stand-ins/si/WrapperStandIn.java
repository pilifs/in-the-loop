package si;

/**
 * The stand-in for {@link Wrapper#set} on a wrapper of exactly that class around a {@link Bean}: the reflective lookup
 * written out for the bean's two setters (a name whose first unit upper-cases to the setter's and whose rest is the
 * property's), and anything else handed back to the method.
 */
public final class WrapperStandIn {

	private WrapperStandIn() {
	}

	public static void set(Wrapper self, String name, String value) {
		Object target = self.getTarget();
		if (target == null || target.getClass() != Bean.class) {
			self.set(name, value);
			return;
		}
		Bean bean = (Bean) target;
		if (name.isEmpty()) {
			return;
		}
		char first = name.charAt(0);
		String rest = name.substring(1);
		if ((first == 'a' || first == 'A') && rest.equals("ge")) {
			bean.setAge(Integer.parseInt(value));
		}
		else if ((first == 'n' || first == 'N') && rest.equals("ame")) {
			bean.setName(value);
		}
	}

	public static void main(String[] args) {
		Samples.print(WrapperStandIn::set);
	}
}
