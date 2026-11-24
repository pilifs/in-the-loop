import com.peterabeles.auto64fto32f.ConvertFile32From64;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
public final class ReferenceAPI {
    static long transform(int n,boolean inputCheck) throws java.io.IOException {
        Path dir=Files.createTempDirectory(Paths.get("."),"numbers-"),old=dir.resolve("Sample_F64.java"),out=dir.resolve("Sample_F32.java");
        String number=n==0?"1.25":"2.5";
        String source="class Sample_F64 { double x = "+number+"; int kept = 7; }\n";
        try {
            Files.write(old,source.getBytes(StandardCharsets.UTF_8));
            new ConvertFile32From64(true).process(old.toFile(),out.toFile());
            String text=new String(Files.readAllBytes(inputCheck?old:out),StandardCharsets.UTF_8);
            return (inputCheck?text.equals(source):text.contains("float x = "+number+"f;") && text.contains("int kept = 7;"))?1:0;
        } finally {Files.deleteIfExists(out);Files.deleteIfExists(old);Files.deleteIfExists(dir);}
    }
    public static long primary(int n) throws java.io.IOException {return transform(n,false);}
    public static long control(int n) throws java.io.IOException {return transform(n,true);}
}
