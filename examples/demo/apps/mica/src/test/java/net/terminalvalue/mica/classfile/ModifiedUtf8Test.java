package net.terminalvalue.mica.classfile;

import static net.terminalvalue.mica.Tests.check;
import static net.terminalvalue.mica.Tests.equal;

public final class ModifiedUtf8Test {

    private ModifiedUtf8Test() {}

    public static void asciiTakesOneByte() {
        equal(1, ModifiedUtf8.encodedLength('a'));
        equal(1, ModifiedUtf8.encodedLength('\u007f'));
        equal(97, ModifiedUtf8.firstByte('a'));
    }

    public static void nulTakesTwoBytes() {
        equal(2, ModifiedUtf8.encodedLength('\u0000'));
        equal(0xc0, ModifiedUtf8.firstByte('\u0000'));
    }

    public static void latinAndCyrillicTakeTwoBytes() {
        equal(2, ModifiedUtf8.encodedLength('é'));
        equal(2, ModifiedUtf8.encodedLength('߿'));
        equal(0xc3, ModifiedUtf8.firstByte('é'));
    }

    public static void theRestOfTheBasicPlaneTakesThree() {
        equal(3, ModifiedUtf8.encodedLength('ࠀ'));
        equal(3, ModifiedUtf8.encodedLength('字'));
        equal(3, ModifiedUtf8.encodedLength('\ud83d')); // a surrogate: three bytes each, six for the pair
        equal(0xe5, ModifiedUtf8.firstByte('字'));
    }

    public static void aStringsLengthIsTheSumOfItsCodeUnits() {
        equal(13, ModifiedUtf8.encodedLengthOf("java/lang/Obj"));
        equal(7, ModifiedUtf8.encodedLengthOf("a\u0000b字"));
    }

    public static void theEncodingOfAsciiIsTheAsciiBytes() {
        byte[] out = new byte[9];
        equal(3, ModifiedUtf8.encodeInto("abc".toCharArray(), out));
        equal((byte) 'a', out[0]);
        equal((byte) 'c', out[2]);
    }

    public static void nulAndTheHigherPlanesAreEncodedAsTheSpecificationSays() {
        byte[] out = new byte[9];
        equal(6, ModifiedUtf8.encodeInto("a\u0000字".toCharArray(), out));
        equal((byte) 0xc0, out[1]);
        equal((byte) 0x80, out[2]);
        equal((byte) 0xe5, out[3]);
        equal((byte) 0xad, out[4]);
        equal((byte) 0x97, out[5]);
        equal((byte) 0x00, out[6]); // untouched
    }

    public static void noFirstByteIsZero() {
        for (char c = 1; c < 256; c++) {
            check(ModifiedUtf8.firstByte(c) != 0, "a zero byte for " + (int) c);
        }
    }
}
