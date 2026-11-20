package bom;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import org.apache.commons.io.ByteOrderMark;
import org.apache.commons.io.input.BOMInputStream;
import org.intheloop.controls.Grid;
import static org.intheloop.controls.Grid.fields;

public final class BomCases {
    public static void main(String[] args) throws Exception {
        int code = 0;
        for (int[] raw : new int[][]{{}, {65}, {97, 44, 98, 10, 99, 44, 100, 10}}) {
            for (boolean bom : new boolean[]{false, true}) {
                for (boolean include : new boolean[]{false, true}) {
                    for (String mode : new String[]{"none", "implicit", "explicit"}) {
                        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                        if (bom) bytes.write(new byte[]{(byte) 239, (byte) 187, (byte) 191});
                        for (int b : raw) bytes.write(b);
                        ByteArrayInputStream delegate = new ByteArrayInputStream(bytes.toByteArray());
                        try (BOMInputStream stream = BOMInputStream.builder().setInputStream(delegate)
                                .setByteOrderMarks(ByteOrderMark.UTF_8).setInclude(include).get()) {
                            if (mode.equals("explicit")) stream.mark(32);
                            if (!mode.equals("none")) {
                                stream.read();
                                stream.reset();
                            }
                            byte[] remaining = stream.readAllBytes();
                            int[] got = new int[remaining.length];
                            for (int i = 0; i < remaining.length; i++) got[i] = remaining[i] & 255;
                            Grid.row(code, fields("payload", raw, "bom", bom, "include", include, "mode", mode),
                                    fields("bytes", got, "eof", stream.read()),
                                    fields("bytes", Projection.bytes(code), "eof", Projection.eof(code)));
                            code++;
                        }
                    }
                }
            }
        }
    }
}
