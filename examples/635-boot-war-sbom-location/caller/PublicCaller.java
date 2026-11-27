import java.nio.file.*;
import java.util.*;
import java.util.jar.*;
import org.springframework.boot.loader.tools.Layouts;

public class PublicCaller {
    public static String observe(String[] args) throws Exception {
        boolean war = !args[0].equals("control");
        String logical = "META-INF/sbom/application.cdx.json";
        String physical = (war ? "WEB-INF/classes/" : "") + logical;
        byte[] selected = PackagingFixture.text("{\"marker\":\"selected\"}");
        Map<String,byte[]> entries = new LinkedHashMap<>();
        if (args[0].equals("challenge")) entries.put("WEB-INF/classes/other/application.cdx.json",PackagingFixture.text("{\"marker\":\"other\"}"));
        entries.put(physical,selected);
        Path archive = PackagingFixture.packageApp(Files.createTempDirectory("sbom"),war,entries,List.of(),null);
        try (var file = new JarFile(archive.toFile())) {
            var attrs = file.getManifest().getMainAttributes();
            String format = Objects.toString(attrs.getValue("Sbom-Format"),"absent");
            String location = Objects.toString(attrs.getValue("Sbom-Location"),"absent");
            if (!war) return format + "/" + location;
            boolean originalPresent = Arrays.equals(PackagingFixture.read(file,physical),selected);
            if (location.equals("absent")) return format + "/absent:" + (originalPresent ? "present" : "missing");
            return format + "/" + location + ":" + (Arrays.equals(PackagingFixture.read(file,location),selected) ? "selected" : "other");
        }
    }
}
