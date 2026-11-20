package measure;

import importer.PageImporter;
import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.util.HexFormat;

/** This producer's runtime classpath contains the application and IO alone. */
public final class IOFact {
    public static void main(String[] args) throws Exception {
        Method open = PageImporter.class.getDeclaredMethod("open", byte[].class, boolean.class, boolean.class);
        open.setAccessible(true);
        BufferedReader cases = java.nio.file.Files.newBufferedReader(java.nio.file.Path.of(args[0]), StandardCharsets.UTF_8);
        String row;
        while ((row = cases.readLine()) != null) {
            String[] in = row.split("\t", -1);
            byte[] supplied = HexFormat.of().parseHex(in[1]);
            boolean narrow = in[2].equals("1"), preview = in[3].equals("1");
            byte[] bytes = PageImporter.remaining(supplied, narrow, preview);
            StringBuilder decoded = new StringBuilder();
            int eof;
            try (InputStream source = (InputStream) open.invoke(null, supplied, narrow, preview);
                 InputStreamReader reader = new InputStreamReader(source, StandardCharsets.UTF_8)) {
                char[] buffer = new char[8];
                int count;
                while ((count = reader.read(buffer, 0, buffer.length)) != -1) decoded.append(buffer, 0, count);
                eof = reader.read();
            }
            System.out.println(in[0] + "\t" + HexFormat.of().formatHex(bytes) + "\t"
                    + HexFormat.of().formatHex(decoded.toString().getBytes(StandardCharsets.UTF_16BE)) + "\t" + eof);
        }
    }
}
