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

    public static void noFirstByteIsZero() {
        for (char c = 1; c < 256; c++) {
            check(ModifiedUtf8.firstByte(c) != 0, "a zero byte for " + (int) c);
        }
    }
}
