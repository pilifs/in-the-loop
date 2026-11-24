import java.io.IOException;

/** The old writer and reader live in before.*, independently of the new release. */
public final class WireClaims {
    static boolean roundTrip(int value, boolean oldWriter, boolean oldReader, boolean equal) throws IOException {
        byte[] frame = {0x33, 0, 0, 0, 0, 0x55};
        int end = oldWriter ? before.WireAPI.write(frame, 1, value) : WireAPI.write(frame, 1, value);
        long read = oldReader ? before.WireAPI.read(frame, 1) : WireAPI.read(frame, 1);
        int expected = equal ? value : Integer.reverseBytes(value);
        boolean palindrome = (byte)value == (byte)(value >>> 24) && (byte)(value >>> 8) == (byte)(value >>> 16);
        return end == 5 && (read >>> 32) == 5 && (int) read == expected && frame[0] == 0x33 && frame[5] == 0x55
                && (oldWriter == oldReader || (((int) read == value) == palindrome));
    }

    public static boolean oldOld(int v) throws IOException { return roundTrip(v, true, true, true); }
    public static boolean oldNew(int v) throws IOException { return roundTrip(v, true, false, false); }
    public static boolean newOld(int v) throws IOException { return roundTrip(v, false, true, false); }
    public static boolean newNew(int v) throws IOException { return roundTrip(v, false, false, true); }
    public static boolean wrongIdentity(int v) throws IOException { return roundTrip(v, true, false, true); }

    /** Any valid four-byte slice. One universally chosen index observes every possible frame byte. */
    public static boolean writeFrame(byte[] entry, int offset, int index, int value) throws IOException {
        if (offset < 0 || offset > entry.length - 4 || index < 0 || index >= entry.length) return true;
        byte[] alias = entry;
        byte old = alias[index];
        int end = WireAPI.write(entry, offset, value);
        int i = index - offset;
        byte expected = i >= 0 && i < 4 ? (byte)(value >>> (8 * i)) : old;
        return alias[index] == expected && end == offset + 4;
    }

    public static boolean readFrame(byte[] entry, int offset, int index) throws IOException {
        if (offset < 0 || offset > entry.length - 4 || index < 0 || index >= entry.length) return true;
        byte[] alias = entry;
        byte old = alias[index];
        int expected = (entry[offset] & 255) | (entry[offset+1] & 255) << 8
                | (entry[offset+2] & 255) << 16 | entry[offset+3] << 24;
        long observed = WireAPI.read(entry, offset);
        return (int) observed == expected && (observed >>> 32) == offset + 4 && alias[index] == old;
    }

    static boolean varint(int value, boolean oldWriter, boolean oldReader) throws IOException {
        byte[] frame = {0x33, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55};
        int end = oldWriter ? before.WireAPI.writeVInt(frame, 1, value) : WireAPI.writeVInt(frame, 1, value);
        int bits = value;
        int pos = 1;
        do {
            int group = bits & 127;
            bits >>>= 7;
            if (frame[pos++] != (byte)(bits == 0 ? group : group | 128)) return false;
        } while (bits != 0);
        long read = oldReader ? before.WireAPI.readVInt(frame, 1) : WireAPI.readVInt(frame, 1);
        return end == pos && (read >>> 32) == pos && (int) read == value && frame[0] == 0x33 && frame[pos] == 0x55;
    }

    public static boolean varOldNew(int v) throws IOException { return varint(v, true, false); }
    public static boolean varNewOld(int v) throws IOException { return varint(v, false, true); }
}
