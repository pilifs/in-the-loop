import org.apache.commons.text.WordUtils;

public final class UpgradeProbe {
    public static String observe(String[] args) {
        return WordUtils.capitalizeFully(args[0], args[1].toCharArray());
    }
}
