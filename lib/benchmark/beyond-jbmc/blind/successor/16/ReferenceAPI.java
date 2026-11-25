import de.rototor.pdfbox.graphics2d.PdfBoxGraphics2D;
import java.awt.Color;
import java.awt.GradientPaint;
import org.apache.pdfbox.cos.*;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.graphics.form.PDFormXObject;

public final class ReferenceAPI {
    private static long draw(int n, boolean box) throws Exception {
        try (PDDocument d = new PDDocument()) {
            PdfBoxGraphics2D g = new PdfBoxGraphics2D(d, 40, 30);
            g.setPaint(new GradientPaint(0, 0, Color.RED, 30, 20, new Color(0, 0, 255, n == 0 ? 255 : 12)));
            g.fillRect(1, 1, 20, 15);
            g.dispose();
            PDFormXObject form = g.getXFormObject();
            if (box) return form.getBBox().getWidth() == 40 && form.getBBox().getHeight() == 30 ? 1 : 0;
            for (COSName name : form.getResources().getExtGStateNames()) {
                COSBase mask = form.getResources().getExtGState(name).getCOSObject().getDictionaryObject(COSName.SMASK);
                if (mask instanceof COSDictionary) return 1;
            }
            return 0;
        }
    }
    public static long primary(int n) throws Exception { return draw(n, false); }
    public static long control(int n) throws Exception { return draw(n, true); }
}
