package sn;

/**
 * The entries. {@code ageAfter} binds "32" to a fresh bean by a name and is the lemma's method; {@code viaLemma} calls
 * it and is the check that uses the lemma; {@code direct} makes the call itself. {@code main} prints what a JVM says
 * of each on "Age".
 */
public final class Use {

	private Use() {
	}

	public static int ageAfter(String name) {
		Bean bean = new Bean();
		new Wrapper(bean).set(name, "32");
		return bean.getAge();
	}

	public static int viaLemma(String name) {
		return ageAfter(name);
	}

	public static void main(String[] args) {
		System.out.println("ageAfter=" + ageAfter("Age") + " viaLemma=" + viaLemma("Age"));
	}
}
