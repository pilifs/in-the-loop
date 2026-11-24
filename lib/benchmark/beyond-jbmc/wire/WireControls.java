import java.util.Arrays;

public final class WireControls {
    public static void main(String[] args) throws Exception {
        for (int v : new int[]{0, 127, 128, 16383, 16384, -1, Integer.MIN_VALUE, 0x01020304, 0x12212112}) {
            if (!(WireClaims.oldOld(v) && WireClaims.oldNew(v) && WireClaims.newOld(v) && WireClaims.newNew(v)
                    && WireClaims.varOldNew(v) && WireClaims.varNewOld(v))) throw new AssertionError(v);
        }
        if (WireClaims.wrongIdentity(0x01020304) || !WireClaims.wrongIdentity(0x12212112)) throw new AssertionError();
        int checks = 0;
        for (int off=0; off<=4; ++off) {
            for (int i=0; i<8; ++i) {
                byte[] buf = {0, -1, 2, -3, 4, -5, 6, -7};
                if (!WireClaims.writeFrame(buf.clone(), off, i, 0x01020304) || !WireClaims.readFrame(buf.clone(), off, i))
                    throw new AssertionError(Arrays.toString(buf));
                ++checks;
            }
        }
        // Mutating the order and the index really changes the byte a reader observes.
        byte[] frame = {0x33, 0, 0, 0, 0, 0x55, 0x55};
        WireAPI.write(frame, 1, 0x01020304);
        if (frame[1] == 1 || frame[1] == 0x55) throw new AssertionError();
        byte[] shifted = {0x33, 0, 0, 0, 0, 0x55, 0x55};
        WireAPI.write(shifted, 2, 0x01020304);
        if (Arrays.equals(frame, shifted) || shifted[5] == 0x55) throw new AssertionError();
        System.out.println("9 fixed-width and VInt seeds; 2 identity controls; " + checks + " slice positions; order and offset controls");
    }
}
