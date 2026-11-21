import java.io.File;
import java.util.Arrays;
import org.languagetool.languagemodel.LuceneLanguageModel;

public final class UpgradeProbe {
    public static String observe(String[] tokens) {
        try (LuceneLanguageModel model = new LuceneLanguageModel(new File("fixtures/ngram-index"))) {
            return Long.toString(model.getCount(Arrays.asList(tokens)));
        }
    }
}
