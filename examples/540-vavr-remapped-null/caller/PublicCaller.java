import io.vavr.collection.HashMap;

public class PublicCaller {
    public static String observe(String[] args) {
        var original = HashMap.of(1, "v");
        int[] calls = {0};
        if (args[0].equals("control")) {
            var r =
                    original.computeIfPresent(
                            2,
                            (k, v) -> {
                                calls[0]++;
                                return "other";
                            });
            return r._1.isDefined() + "/" + calls[0] + "/" + r._2.size() + "/" + r._2.get(1).get();
        }
        var r = original.computeIfPresent(1, (k, v) -> null);
        if (args[0].equals("intent"))
            return r._1.isDefined()
                    + "/"
                    + (r._1.isDefined() ? r._1.get() : "-")
                    + "/"
                    + r._2.containsKey(1)
                    + "/"
                    + r._2.get(1).get();
        String[] seen = {""};
        var second =
                r._2.computeIfPresent(
                        1,
                        (k, v) -> {
                            seen[0] = "(" + k + "," + v + ")";
                            calls[0]++;
                            return "restored";
                        });
        return seen[0]
                + "/"
                + calls[0]
                + "/"
                + second._1.get()
                + "/"
                + second._2.get(1).get()
                + "/"
                + original.get(1).get();
    }
}
