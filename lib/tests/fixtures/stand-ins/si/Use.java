package si;

/** The entries the tests prove or refute, each binding one property value "32" by its name. */
public final class Use {

	private Use() {
	}

	public static int ageAfter(String name) {
		Bean bean = new Bean();
		new Wrapper(bean).set(name, "32");
		return bean.getAge();
	}

	public static int ageAfterLoud(String name) {
		Bean bean = new Bean();
		new Loud(bean).set(name, "32");
		return bean.getAge();
	}

	public static int otherAfter(String name) {
		Other other = new Other();
		new Wrapper(other).set(name, "32");
		return other.getAge();
	}
}
