package si;

/** A stand-in with a public static helper that stands in for nothing: it is refused, not taken for a helper. */
public final class HelperStandIn {

	private HelperStandIn() {
	}

	public static void set(Wrapper self, String name, String value) {
		self.set(name, value);
	}

	public static int twice(Bean bean, int x) {
		return 2 * x;
	}

	public static void main(String[] args) {
		Samples.print(HelperStandIn::set);
	}
}
