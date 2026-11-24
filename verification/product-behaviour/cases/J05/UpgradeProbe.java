import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.util.HashMap;
import java.util.Map;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;
import javax.xml.parsers.DocumentBuilderFactory;
import org.apache.poi.common.usermodel.HyperlinkType;
import org.apache.poi.xssf.usermodel.*;
import org.w3c.dom.Element;

public class UpgradeProbe {
    private static final String URL = "https://example.com/page";
    private static final String KEEP = "https://example.org/untouched";
    private static byte[] save(XSSFWorkbook wb) throws Exception {
        try (ByteArrayOutputStream out = new ByteArrayOutputStream()) { wb.write(out); return out.toByteArray(); }
    }
    private static void seed(XSSFSheet sheet, String address, boolean section) {
        XSSFHyperlink link = sheet.getWorkbook().getCreationHelper().createHyperlink(HyperlinkType.URL);
        link.setAddress(address);
        if (section) link.setLocation("section");
        sheet.createRow(0).createCell(0).setHyperlink(link);
        sheet.createRow(1).createCell(0);
    }
    private static String address(XSSFSheet sheet, int row) {
        XSSFHyperlink link = sheet.getRow(row).getCell(0).getHyperlink();
        return link == null ? "-" : link.getAddress();
    }
    private static Element xml(byte[] bytes) throws Exception {
        var factory = DocumentBuilderFactory.newInstance();
        factory.setNamespaceAware(true);
        return factory.newDocumentBuilder().parse(new ByteArrayInputStream(bytes)).getDocumentElement();
    }
    private static String relationship(byte[] file, int sheet, String cell) throws Exception {
        Map<String, byte[]> parts = new HashMap<>();
        try (var archive = new ZipInputStream(new ByteArrayInputStream(file))) {
            for (ZipEntry e; (e = archive.getNextEntry()) != null;)
                if (e.getName().startsWith("xl/worksheets/")) parts.put(e.getName(), archive.readAllBytes());
        }
        String part = "sheet" + sheet + ".xml";
        var links = xml(parts.get("xl/worksheets/" + part)).getElementsByTagNameNS("*", "hyperlink");
        for (int i = 0; i < links.getLength(); i++) {
            Element link = (Element) links.item(i);
            if (!cell.equals(link.getAttribute("ref"))) continue;
            String id = link.getAttributeNS("http://schemas.openxmlformats.org/officeDocument/2006/relationships", "id");
            byte[] rels = parts.get("xl/worksheets/_rels/" + part + ".rels");
            if (rels != null && !id.isEmpty()) {
                var targets = xml(rels).getElementsByTagNameNS("*", "Relationship");
                for (int j = 0; j < targets.getLength(); j++) {
                    Element target = (Element) targets.item(j);
                    if (id.equals(target.getAttribute("Id")) && "External".equals(target.getAttribute("TargetMode")))
                        return target.getAttribute("Target");
                }
            }
            return "unresolved";
        }
        return "-";
    }
    public static String observe(String[] args) throws Exception {
        boolean move = args[0].equals("move"), section = args[1].equals("section");
        byte[] first;
        try (XSSFWorkbook seed = new XSSFWorkbook()) {
            seed(seed.createSheet("target"), URL, section);
            seed(seed.createSheet("untouched"), KEEP, false);
            first = save(seed);
        }
        byte[] second;
        try (XSSFWorkbook loaded = new XSSFWorkbook(new ByteArrayInputStream(first))) {
            XSSFSheet sheet = loaded.getSheet("target");
            XSSFCell a1 = sheet.getRow(0).getCell(0);
            XSSFHyperlink link = a1.getHyperlink();
            if (!link.getAddress().equals(URL + (section ? "#section" : ""))) throw new AssertionError("initial target");
            if (move) { a1.removeHyperlink(); sheet.getRow(1).getCell(0).setHyperlink(link); }
            second = save(loaded);
        }
        String cell = move ? "A2" : "A1";
        String raw = relationship(second, 1, cell);
        if (!KEEP.equals(relationship(second, 2, "A1"))) throw new AssertionError("untouched sheet relationship");
        int opening = 2;
        try (XSSFWorkbook twice = new XSSFWorkbook(new ByteArrayInputStream(second))) {
            XSSFSheet original = twice.getSheet("target");
            String state = address(original, 0) + "/" + address(original, 1);
            if (!KEEP.equals(address(twice.getSheet("untouched"), 0))) throw new AssertionError("untouched second read");
            twice.cloneSheet(0);
            byte[] third = save(twice);
            opening = 3;
            try (XSSFWorkbook again = new XSSFWorkbook(new ByteArrayInputStream(third))) {
                if (!KEEP.equals(address(again.getSheet("untouched"), 0)) || !KEEP.equals(relationship(third, 2, "A1")))
                    throw new AssertionError("untouched third read");
                return raw + "|" + state + "|" + address(again.getSheetAt(0), move ? 1 : 0)
                        + "|" + address(again.getSheetAt(2), move ? 1 : 0) + "|" + relationship(third, 3, cell);
            }
        } catch (IllegalStateException failure) {
            if (!failure.getMessage().contains("hyperlink for cell " + cell)) throw failure;
            return raw + "|reopen" + opening + ":" + failure.getClass().getSimpleName() + ":" + cell;
        }
    }
}
