import java.lang.reflect.Field;
import java.net.URI;
import java.nio.ByteBuffer;
import java.nio.CharBuffer;
import java.nio.charset.Charset;
import java.nio.charset.CharsetEncoder;
import java.nio.charset.StandardCharsets;
import java.util.HexFormat;
import org.apache.commons.io.input.CharSequenceInputStream;

/** Inspect positions between public calls without changing the stream, its buffers or its encoder. */
public final class CharsetPositions {
    private static Object field(CharSequenceInputStream stream, String name) throws Exception {
        Field field = CharSequenceInputStream.class.getDeclaredField(name);
        field.setAccessible(true);
        return field.get(stream);
    }

    private static String state(CharSequenceInputStream stream) throws Exception {
        ByteBuffer bytes = (ByteBuffer)field(stream, "bBuf");
        CharBuffer chars = (CharBuffer)field(stream, "cBuf");
        byte[] remaining = new byte[bytes.remaining()];
        bytes.asReadOnlyBuffer().get(remaining);
        return field(stream, "cBufMark") + "," + field(stream, "bBufMark") + ","
                + chars.position() + "," + bytes.position() + "," + chars.limit() + "," + bytes.limit()
                + "," + HexFormat.of().formatHex(remaining);
    }

    public static void main(String[] args) throws Exception {
        Charset selected = args[1].equals("explicit") ? StandardCharsets.UTF_8 : null;
        CharSequenceInputStream stream = new CharSequenceInputStream("Aé中Z", selected, 8);
        CharsetEncoder encoder = (CharsetEncoder)field(stream, "charsetEncoder");
        URI jar = CharSequenceInputStream.class.getProtectionDomain().getCodeSource().getLocation().toURI();
        System.out.println("source\t" + java.nio.file.Path.of(jar));
        System.out.println("default\t" + Charset.defaultCharset().name());
        System.out.println("encoder\t" + encoder.charset().name());
        System.out.println("buffers\t" + field(stream, "cBuf").getClass().getName() + "," + field(stream, "bBuf").getClass().getName());
        // The first output is the byte-identical original plan observer, executed in this very process.
        System.out.println("observation\t" + UpgradeProbe.observe(args));
        if (stream.read() != 'A') throw new AssertionError("wrong prefix");
        stream.mark(16);
        System.out.println("marked\t" + state(stream));
        byte[] destination = new byte[5];
        for (int i = 0; i < 32; i++) {
            String before = state(stream);
            int count = stream.read(destination, 1, 3);
            String read = state(stream);
            stream.reset();
            System.out.println("cycle\t" + before + "\t" + count + "\t" + read + "\t" + state(stream));
        }
    }
}
