import java.awt.image.BufferedImage;
import java.io.File;
import javax.imageio.ImageIO;
import net.glxn.qrgen.javase.QRCode;
import com.google.zxing.*;
import com.google.zxing.common.HybridBinarizer;

public final class UpgradeProbe {
    public static String observe(String[] args) throws Exception {
        File output = QRCode.from(args[0]).file();
        BufferedImage image = ImageIO.read(output);
        if (image == null) return null;
        int w = image.getWidth(), h = image.getHeight();
        int[] pixels = image.getRGB(0, 0, w, h, null, 0, w);
        BinaryBitmap bitmap = new BinaryBitmap(new HybridBinarizer(new RGBLuminanceSource(w, h, pixels)));
        return new MultiFormatReader().decode(bitmap).getText();
    }
}
