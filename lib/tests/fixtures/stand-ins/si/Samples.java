package si;

import java.util.ArrayList;
import java.util.List;
import java.util.function.BiConsumer;

/** What every sampler of this fixture does: each name and value on fresh beans, through the method and through a stand-in. */
final class Samples {

	private Samples() {
	}

	static List<String> names() {
		List<String> names = new ArrayList<>(List.of("", "age", "Age", "AGE", "aGe", "agE", "name", "Name", "NAME", "nam", "agee", "ages", "target", "Target", "class", "Class"));
		String alphabet = "aAgenNx";
		for (int i = 0; i < alphabet.length(); i++) {
			names.add(alphabet.substring(i, i + 1));
			for (int j = 0; j < alphabet.length(); j++) {
				names.add(alphabet.substring(i, i + 1) + alphabet.charAt(j));
			}
		}
		return names;
	}

	/** One line per name and value: the method's outcome, then {@code standIn}'s, on a fresh bean each. */
	static void print(StandIn standIn) {
		for (String name : names()) {
			for (String value : new String[] {"32", "-1", "x", ""}) {
				String input = "name=" + name + " value=" + value;
				System.out.println("sample\t" + input + "\t" + outcome((w, unused) -> w.set(name, value)) + "\t" + outcome((w, unused) -> standIn.set(w, name, value)));
			}
		}
	}

	interface StandIn {
		void set(Wrapper self, String name, String value);
	}

	private static String outcome(BiConsumer<Wrapper, Void> call) {
		Bean bean = new Bean();
		String threw = "none";
		try {
			call.accept(new Wrapper(bean), null);
		}
		catch (RuntimeException ex) {
			threw = ex.getClass().getName();
		}
		return "threw=" + threw + " age=" + bean.getAge() + " name=" + bean.getName();
	}
}
