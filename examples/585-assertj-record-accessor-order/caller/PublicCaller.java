import org.assertj.core.api.Assertions;

public class PublicCaller {
    public record Plain(String field, boolean isField) {}

    public record WithGetter(String field, boolean isField) {
        public String getField() {
            return "fixed";
        }
    }

    static boolean accepts(Object left, Object right, boolean equal) {
        try {
            var check = Assertions.assertThat(left).usingRecursiveComparison();
            if (equal) check.isEqualTo(right);
            else check.isNotEqualTo(right);
            return true;
        } catch (AssertionError expected) {
            return false;
        }
    }

    public static String observe(String[] a) {
        if (a[0].equals("challenge")) {
            var x = new WithGetter("one", true);
            var y = new WithGetter("two", true);
            return "field="
                    + x.field()
                    + "/"
                    + y.field()
                    + ",getter="
                    + x.getField()
                    + "/"
                    + y.getField()
                    + ",equal="
                    + accepts(x, y, true);
        }
        boolean control = a[0].equals("control");
        var x = new Plain("one", true);
        var y = new Plain(control ? "one" : "two", true);
        return "equal=" + accepts(x, y, true) + (control ? "" : ",unequal=" + accepts(x, y, false));
    }
}
