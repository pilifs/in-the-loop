package invoice;

import java.io.InputStream;
import java.nio.file.Path;
import java.security.MessageDigest;

public final class Invoices {
    private static String digest(Class<?> type) throws Exception {
        try (InputStream bytes = type.getResourceAsStream(type.getSimpleName() + ".class")) {
            byte[] hash = MessageDigest.getInstance("SHA-256").digest(bytes.readAllBytes());
            StringBuilder hex = new StringBuilder();
            for (byte b : hash) hex.append(String.format("%02x", b));
            return hex.toString();
        }
    }

    public static void main(String[] args) throws Exception {
        Path origin = Path.of(Rate.class.getProtectionDomain().getCodeSource().getLocation().toURI());
        for (int q = -2; q <= 2; q++) {
            System.out.printf("{\"q\":%d,\"total\":%d,\"rateJar\":\"%s\",\"rateClass\":\"%s\",\"invoiceClass\":\"%s\"}%n",
                    q, Invoice.total(q), origin.getFileName(), digest(Rate.class), digest(Invoice.class));
        }
    }
}
