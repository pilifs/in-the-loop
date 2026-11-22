import datawork.ToleranceSearch;
import java.io.BufferedOutputStream;
import java.io.DataOutputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.zip.GZIPOutputStream;
import org.apache.commons.lang3.ArrayUtils;

public final class ToleranceReplay {
    public static void main(String[] args) throws Exception {
        String[] indices = args[2].split(",");
        int[] starts = new int[indices.length];
        for (int i = 0; i < starts.length; i++) starts[i] = Integer.parseInt(indices[i]);
        long[] words = new long[args.length - 3];
        for (int i = 0; i < words.length; i++) words[i] = Long.parseUnsignedLong(args[i + 3], 16);

        try (var out = new DataOutputStream(new BufferedOutputStream(
                new GZIPOutputStream(Files.newOutputStream(Path.of(args[1])))))) {
            for (int center = -1; center <= 1; center++) {
                for (long first : words) {
                    for (long second : words) {
                        for (int start : starts) {
                            double[] values = {Double.longBitsToDouble(ToleranceSearch.cellBits(first)),
                                    Double.longBitsToDouble(ToleranceSearch.cellBits(second))};
                            out.writeInt(ArrayUtils.indexOf(values, center * 0.5, start, 0.25));
                            out.writeLong(Double.doubleToRawLongBits(values[0]));
                            out.writeLong(Double.doubleToRawLongBits(values[1]));
                            out.writeByte(ToleranceSearch.agrees(first, second, start, center));
                        }
                    }
                }
            }
        }
        LoadedClasses.main(new String[]{args[0], ToleranceSearch.class.getName(), ArrayUtils.class.getName()});
    }
}
