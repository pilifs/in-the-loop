import java.nio.file.Files;
import java.nio.file.Path;

public final class WirePair {
    public static void main(String[] args) throws Exception {
        Path file = Path.of(args[1]);
        if (args[0].equals("write")) {
            byte[] frame = {0x33, 0, 0, 0, 0, 0x55};
            int end = WireAPI.write(frame, 1, 0x01020304);
            if (end != 5 || frame[0] != 0x33 || frame[5] != 0x55) throw new AssertionError();
            Files.write(file, frame);
        } else {
            long result = WireAPI.read(Files.readAllBytes(file), 1);
            if ((result >>> 32) != 5) throw new AssertionError();
            System.out.printf("%08x%n", (int) result);
        }
    }
}
