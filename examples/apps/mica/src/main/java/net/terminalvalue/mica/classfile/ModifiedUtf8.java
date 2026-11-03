package net.terminalvalue.mica.classfile;

/**
 * The encoding of {@code CONSTANT_Utf8_info} (JVMS §4.4.7): UTF-8, except that the character U+0000 takes the
 * two-byte form and supplementary characters are encoded as their two surrogates, three bytes each. The two
 * exceptions have one purpose: no byte of an encoded string is zero, so that the virtual machine can hand the
 * bytes to C code as a string and count them without decoding. A zero byte in a {@code CONSTANT_Utf8_info} is a
 * {@code ClassFormatError}.
 */
public final class ModifiedUtf8 {

    private ModifiedUtf8() {}

    /** How many bytes the UTF-16 code unit {@code c} takes: one, two or three. */
    public static int encodedLength(char c) {
        if (c >= 0x0001 && c <= 0x007f) {
            return 1;
        }
        return c <= 0x07ff ? 2 : 3;
    }

    /** How many bytes {@code s} takes, which is what the {@code length} field of the constant holds. */
    public static int encodedLengthOf(CharSequence s) {
        int length = 0;
        for (int i = 0; i < s.length(); i++) {
            length += encodedLength(s.charAt(i));
        }
        return length;
    }

    /** The first byte of the encoding of {@code c}, as an unsigned value. */
    public static int firstByte(char c) {
        if (c >= 0x0001 && c <= 0x007f) {
            return c;
        }
        if (c <= 0x07ff) {
            return 0xc0 | (c >> 6);
        }
        return 0xe0 | (c >> 12);
    }

    /**
     * Writes the encoding of {@code chars} into {@code out}, which must hold {@code 3 * chars.length} bytes, and
     * returns how many bytes it wrote: the {@code bytes} of the constant. Each UTF-16 code unit is encoded on its
     * own, a surrogate included, so a supplementary character takes six bytes.
     */
    public static int encodeInto(char[] chars, byte[] out) {
        int k = 0;
        for (char c : chars) {
            if (c >= 0x0001 && c <= 0x007f) {
                out[k++] = (byte) c;
            } else if (c <= 0x07ff) {
                out[k++] = (byte) (0xc0 | (c >> 6));
                out[k++] = (byte) (0x80 | (c & 0x3f));
            } else {
                out[k++] = (byte) (0xe0 | (c >> 12));
                out[k++] = (byte) (0x80 | ((c >> 6) & 0x3f));
                out[k++] = (byte) (0x80 | (c & 0x3f));
            }
        }
        return k;
    }
}
