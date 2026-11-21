import java.io.File;
import java.nio.file.*;
import java.util.Collections;
import net.masterthought.cucumber.Configuration;
import net.masterthought.cucumber.ReportBuilder;
import net.masterthought.cucumber.Reportable;

public final class UpgradeProbe {
    public static String observe(String[] args) throws Exception {
        Path target = Paths.get("report");
        Files.createDirectories(target);
        Configuration config = new Configuration(target.toFile(),"Upgrade example");
        ReportBuilder builder = new ReportBuilder(Collections.singletonList(Paths.get("fixtures",args[0]).toString()), config);
        Reportable status = builder.generateReports();
        if (status == null) return null;
        Path overview = target.resolve("cucumber-html-reports").resolve("overview-features.html");
        return status.getFeatures()+"/"+status.getSteps()+"/"+status.getPassedSteps()+"/"+Files.isRegularFile(overview);
    }
}
