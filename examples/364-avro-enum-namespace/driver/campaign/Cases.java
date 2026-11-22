package campaign;
import static org.intheloop.controls.Grid.*;

public final class Cases {
    public static void main(String[] args) throws Exception {
        for (int code = 0; code < 4; code++) {
            row(code, fields("wire", (code & 1) * 2, "reversed", (code & 2) != 0),
                fields("renamed", EnumReader.read(code, "E", "reader"), "preserved",
                    new String[]{EnumReader.read(code, "E", "writer"), EnumReader.read(code, "Other", "reader")}),
                fields("renamed", EnumReader.renamed(code), "preserved", EnumReader.preserved(code)));
        }
    }
}
