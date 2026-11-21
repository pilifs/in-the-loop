import org.apache.commons.compress.compressors.lz4.FramedLZ4CompressorInputStream;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.util.Base64;

public final class UpgradeProbe {
    public static String observe(String[] args) throws Exception {
        byte[] frame = Base64.getDecoder().decode(args[0]);
        try (FramedLZ4CompressorInputStream in = new FramedLZ4CompressorInputStream(new ByteArrayInputStream(frame))) {
            ByteArrayOutputStream result = new ByteArrayOutputStream();
            int value;
            while ((value = in.read()) != -1) result.write(value);
            return Base64.getEncoder().encodeToString(result.toByteArray());
        }
    }
}
