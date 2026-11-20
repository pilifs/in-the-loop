import java.io.File;
import java.util.Arrays;
import java.util.Collections;
import java.util.Properties;
import org.apache.maven.plugin.surefire.StartupReportConfiguration;
import org.apache.maven.plugin.surefire.report.DefaultReporterFactory;
import org.apache.maven.surefire.booter.BaseProviderFactory;
import org.apache.maven.surefire.junit4.JUnit4Provider;
import org.apache.maven.surefire.suite.RunResult;
import org.apache.maven.surefire.testset.DirectoryScannerParameters;
import org.apache.maven.surefire.testset.RunOrderParameters;
import org.apache.maven.surefire.testset.TestRequest;
import org.apache.maven.surefire.util.DefaultScanResult;

/** Invoke Maven 3.6.3's default JUnit4 provider and XML reporter directly on the unedited upstream class. */
public final class NamedSurefire {
    public static void main(String[] args) throws Exception {
        File reports = new File(System.getProperty("calibration.reports", "target/surefire-reports"));
        if (reports.exists() || !reports.mkdirs()) {
            throw new IllegalStateException("Need a new Surefire report directory");
        }
        StartupReportConfiguration config = new StartupReportConfiguration(
                true, true, "plain", false, false, reports, false, null, "calibration", false);
        DefaultReporterFactory reporter = new DefaultReporterFactory(config);
        BaseProviderFactory parameters = new BaseProviderFactory(reporter, false);
        ClassLoader loader = NamedSurefire.class.getClassLoader();
        parameters.setClassLoaders(loader, loader);
        boolean suite = args[0].equals("--suite");
        Properties properties = new Properties();
        if (suite) {
            new DefaultScanResult(Arrays.asList(args).subList(1, args.length)).writeTo(properties);
            parameters.setDirectoryScannerParameters(new DirectoryScannerParameters(
                    new File("."), Collections.emptyList(), Collections.emptyList(),
                    Collections.emptyList(), true, "filesystem"));
        }
        parameters.setProviderProperties(properties);
        parameters.setRunOrderParameters(RunOrderParameters.DEFAULT());
        parameters.setTestRequest(new TestRequest(Collections.emptyList(), null, suite ? null : args[0], suite ? null : args[1]));
        RunResult result = new JUnit4Provider(parameters).invoke(suite ? null : loader.loadClass(args[0]));
        if (result.getCompletedCount() == 0 || (!suite && (result.getCompletedCount() != 1 || result.getSkipped() != 0))) {
            throw new IllegalStateException("Unexpected testcase count " + result.getAsString());
        }
        System.exit(result.isErrorFree() ? 0 : 1);
    }
}
