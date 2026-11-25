import java.util.List;
import com.github.difflib.DiffUtils;
import com.github.difflib.text.DiffRowGenerator;

public class PublicCaller {
    static String render(boolean explicit, boolean decorate) {
        var old = decorate ? List.of("same", "before", "tail") : List.of("same", "before");
        var updated = decorate ? List.of("same", "after", "tail") : List.of("same", "after");
        var builder = DiffRowGenerator.create().showInlineDiffs(false);
        if (decorate) builder.processEqualities(s -> "EQ-" + s);
        return builder.build().generateDiffRows(old, DiffUtils.diff(old, updated, explicit)).stream()
                .map(r -> r.getTag() + "/" + r.getOldLine() + "/" + r.getNewLine()).toList().toString();
    }

    public static String observe(String[] args) {
        if (args[0].equals("decorated")) return render(true, true) + " | " + render(false, true);
        return render(args[0].equals("explicit"), false);
    }
}
