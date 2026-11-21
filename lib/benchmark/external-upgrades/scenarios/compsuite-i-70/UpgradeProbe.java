import com.monitorjbl.xlsx.StreamingReader;
import com.monitorjbl.xlsx.impl.StreamingCell;
import java.io.*;
import java.nio.file.*;
import org.apache.poi.ss.usermodel.*;

public final class UpgradeProbe {
    public static String observe(String[] input) throws Exception {
        try (InputStream stream = Files.newInputStream(Paths.get("fixtures",input[0]));
             Workbook book = StreamingReader.builder().open(stream)) {
            StreamingCell cell = (StreamingCell) book.getSheetAt(0).iterator().next().getCell(0);
            CellStyle style = cell.getCellStyle();
            return book.getNumberOfSheets() + "/" + cell.getCellTypeEnum() + "/" + (style != null);
        }
    }
}
