package net.terminalvalue.contracts;

import java.io.IOException;
import java.nio.file.Path;

/** Keep the normal repository relocation for the old definition and all of its application callees. */
public final class PairClasses {
    public static void main(String[] args) throws IOException {
        Relocate.directory(Path.of(args[0]), Path.of(args[1]), "before");
    }
}
