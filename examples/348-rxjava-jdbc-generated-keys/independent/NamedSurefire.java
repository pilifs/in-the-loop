import java.io.File;
import java.util.Collections;
import java.util.Properties;
import org.apache.maven.plugin.surefire.StartupReportConfiguration;
import org.apache.maven.plugin.surefire.report.DefaultReporterFactory;
import org.apache.maven.surefire.booter.BaseProviderFactory;
import org.apache.maven.surefire.junit4.JUnit4Provider;
import org.apache.maven.surefire.suite.RunResult;
import org.apache.maven.surefire.testset.RunOrderParameters;
import org.apache.maven.surefire.testset.TestRequest;

/** Invoke Maven 3.6.3's default JUnit4 provider and XML reporter directly on the unedited upstream class. */
public final class NamedSurefire {
    public static void main(String[] args) throws Exception {
        File reports = new File("target/surefire-reports");
        if (reports.exists() || !reports.mkdirs()) {
            throw new IllegalStateException("Need a new Surefire report directory");
        }
        StartupReportConfiguration config = new StartupReportConfiguration(
                true, true, "plain", false, false, reports, false, null, "calibration", false);
        DefaultReporterFactory reporter = new DefaultReporterFactory(config);
        BaseProviderFactory parameters = new BaseProviderFactory(reporter, false);
        ClassLoader loader = NamedSurefire.class.getClassLoader();
        parameters.setClassLoaders(loader, loader);
        parameters.setProviderProperties(new Properties());
        parameters.setRunOrderParameters(RunOrderParameters.DEFAULT());
        parameters.setTestRequest(new TestRequest(Collections.emptyList(), null, args[0], args[1]));
        RunResult result = new JUnit4Provider(parameters).invoke(loader.loadClass(args[0]));
        if (result.getCompletedCount() != 1 || result.getSkipped() != 0) {
            throw new IllegalStateException("Named testcase count " + result.getAsString());
        }
        System.exit(result.isErrorFree() ? 0 : 1);
    }
}
