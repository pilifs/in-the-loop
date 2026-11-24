import java.util.*;
import org.apache.maven.artifact.versioning.*;

public class UpgradeProbe {
    private static final int[][] ORDERS = {{0,1,2},{0,2,1},{1,0,2},{1,2,0},{2,0,1},{2,1,0}};
    public static String observe(String[] args) throws Exception {
        boolean cycle = args[0].equals("qualifiers");
        String[] versions = cycle ? new String[]{"0-alpha","0","x"} : new String[]{"1-alpha","1-beta","1-beta"};
        String spec = cycle ? "[0-alpha,x]" : "[1-alpha,1-beta]";
        VersionRange range = null;
        String construction = "ok";
        try { range = VersionRange.createFromVersionSpec(spec); }
        catch (InvalidVersionSpecificationException e) { construction = e.getClass().getSimpleName(); }
        StringJoiner results = new StringJoiner("|");
        for (int[] order : ORDERS) {
            List<ArtifactVersion> candidates = new ArrayList<>();
            ComparableVersion highest = null;
            for (int i : order) {
                candidates.add(new DefaultArtifactVersion(versions[i]));
                ComparableVersion next = new ComparableVersion(versions[i]);
                if (highest == null || next.compareTo(highest) > 0) highest = next;
            }
            results.add((range == null ? "-" : range.matchVersion(candidates).toString()) + "/" + highest);
        }
        return construction + "|" + results;
    }
}
