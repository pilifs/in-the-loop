import com.monitorjbl.xlsx.StreamingReader;
import java.io.InputStream;
import java.nio.file.*;
import org.apache.poi.ss.usermodel.Workbook;

public final class UpgradeProbe {
    public static String observe(String[] args) throws Exception {
        try (InputStream bytes = Files.newInputStream(Paths.get("fixtures", args[0]));
             Workbook book = StreamingReader.builder().open(bytes)) {
            return Integer.toString(book.getNumberOfSheets());
        }
    }
}
