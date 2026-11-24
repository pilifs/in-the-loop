import java.io.*;
import javax.imageio.ImageIO;
import org.apache.batik.transcoder.*;
import org.apache.batik.transcoder.image.PNGTranscoder;
public final class ReferenceAPI {
    static long render(int n,boolean explicit) {
        int width=n==0?8:16;
        String stop=explicit?" offset='0%'":"";
        String svg="<svg xmlns='http://www.w3.org/2000/svg' width='"+width+"' height='8'><defs><linearGradient id='g'><stop"+stop+" stop-color='red'/><stop offset='100%' stop-color='blue'/></linearGradient></defs><rect width='100%' height='100%' fill='url(#g)'/></svg>";
        ByteArrayOutputStream sink=new ByteArrayOutputStream();
        try {
            new PNGTranscoder().transcode(new TranscoderInput(new StringReader(svg)),new TranscoderOutput(sink));
            java.awt.image.BufferedImage image=ImageIO.read(new ByteArrayInputStream(sink.toByteArray()));
            return image!=null && image.getWidth()==width && image.getHeight()==8?1:2;
        } catch (TranscoderException failure) {return 0;}
        catch (IOException failure) {throw new IllegalStateException(failure);}
    }
    public static long primary(int n) {return render(n,false);}
    public static long control(int n) {return render(n,true);}
}
