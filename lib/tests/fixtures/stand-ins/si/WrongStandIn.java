package si;

/** A stand-in that forgets the upper-cased first unit: "Age" writes age through the method and not through it. */
public final class WrongStandIn {

	private WrongStandIn() {
	}

	public static void set(Wrapper self, String name, String value) {
		Object target = self.getTarget();
		if (target == null || target.getClass() != Bean.class) {
			self.set(name, value);
			return;
		}
		Bean bean = (Bean) target;
		if (name.equals("age")) {
			bean.setAge(Integer.parseInt(value));
		}
		else if (name.equals("name")) {
			bean.setName(value);
		}
	}

	public static void main(String[] args) {
		Samples.print(WrongStandIn::set);
	}
}
