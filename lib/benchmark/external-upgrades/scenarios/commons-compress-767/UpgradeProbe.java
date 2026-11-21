import org.apache.commons.compress.compressors.xz.XZCompressorInputStream;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.util.Base64;

public final class UpgradeProbe {
    public static String observe(String[] args) throws Exception {
        byte[] frame = Base64.getDecoder().decode(args[0]);
        try (XZCompressorInputStream in = new XZCompressorInputStream(new ByteArrayInputStream(frame))) {
            ByteArrayOutputStream result = new ByteArrayOutputStream();
            int value;
            while ((value = in.read()) != -1) result.write(value);
            return Base64.getEncoder().encodeToString(result.toByteArray());
        }
    }
}
