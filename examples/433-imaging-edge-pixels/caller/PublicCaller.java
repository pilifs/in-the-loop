import java.awt.image.BufferedImage;
import java.io.File;
import java.util.ArrayList;
import org.apache.commons.imaging.Imaging;
import org.apache.commons.imaging.formats.tiff.*;

public class PublicCaller {
    static File fixture(String name) { return new File("fixtures", name + ".tiff"); }

    static int luminance(int p) {
        return (int) Math.floor(.299 * ((p >>> 16) & 255) + .587 * ((p >>> 8) & 255) + .114 * (p & 255) + .5);
    }
    public static String observe(String[] args) throws Exception {
        boolean control = args[0].equals("control");
        var imageFile = fixture(control ? "TestJpegTiles264x264" : "TestJpegRgb127x127");
        BufferedImage image = Imaging.getBufferedImage(imageFile);
        if (args[0].equals("corner")) {
            var params = new TiffImagingParameters();
            params.setSubImage(124,125,3,2);
            var region = new TiffImageParser().getBufferedImage(imageFile, params);
            var actual = new ArrayList<Integer>();
            var full = new ArrayList<Integer>();
            for (int j=0; j<2; j++) for (int i=0; i<3; i++) {
                actual.add(region.getRGB(i,j));
                full.add(image.getRGB(124+i,125+j));
            }
            return region.getWidth() + "x" + region.getHeight() + " equal=" + actual.equals(full)
                    + " region=" + actual + " whole=" + full;
        }
        var reference = Imaging.getBufferedImage(fixture(control ? "TestSample264x264" : "TestSampleRgb127x127"));
        int bad=0, maxAlpha=0, maxLuma=0;
        for (int y=0; y<image.getHeight(); y++) for (int x=0; x<image.getWidth(); x++) {
            int p=image.getRGB(x,y), q=reference.getRGB(x,y);
            int a=Math.abs((p >>> 24)-(q >>> 24)), l=Math.abs(luminance(p)-luminance(q));
            maxAlpha=Math.max(maxAlpha,a);
            maxLuma=Math.max(maxLuma,l);
            if (a>1 || l>4) bad++;
        }
        return image.getWidth()+"x"+image.getHeight()+" reference="+reference.getWidth()+"x"+reference.getHeight()
                +" bad="+bad+" maxAlpha="+maxAlpha+" maxLuma="+maxLuma;
    }
}
