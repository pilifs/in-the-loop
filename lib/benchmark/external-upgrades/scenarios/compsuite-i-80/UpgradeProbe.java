import org.zeroturnaround.exec.stream.slf4j.Slf4jInfoOutputStream;
import org.zeroturnaround.exec.stream.slf4j.Slf4jStream;

public final class UpgradeProbe {
    public static String observe(String[] args) {
        Slf4jStream stream = Slf4jStream.of(args[0]);
        return ((Slf4jInfoOutputStream) stream.asInfo()).getLogger().getName();
    }
}
