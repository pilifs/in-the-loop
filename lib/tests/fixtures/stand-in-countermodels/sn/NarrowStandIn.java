package sn;

/**
 * A stand-in for {@link Wrapper#set} on a wrapper around a {@link Bean} that takes the names as written ("age" and
 * "name") and ignores any other. Its sampler is honest but narrow: it compares the bean's whole state and the
 * exception, on four names that each agree, and never tries "Age", which the method writes and the stand-in ignores.
 * The tool takes it, sampled four times, and a result that makes the call says it rests on it.
 */
public final class NarrowStandIn {

	private NarrowStandIn() {
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
		for (String name : new String[] {"age", "name", "x", ""}) {
			System.out.println("sample\tname=" + name + " value=32\t" + outcome(name, false) + "\t" + outcome(name, true));
		}
	}

	private static String outcome(String name, boolean standIn) {
		Bean bean = new Bean();
		Wrapper wrapper = new Wrapper(bean);
		String threw = "none";
		try {
			if (standIn) {
				set(wrapper, name, "32");
			}
			else {
				wrapper.set(name, "32");
			}
		}
		catch (RuntimeException ex) {
			threw = ex.getClass().getName();
		}
		return "threw=" + threw + " age=" + bean.getAge() + " name=" + bean.getName();
	}
}
