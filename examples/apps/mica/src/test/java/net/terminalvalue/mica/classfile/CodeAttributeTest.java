package net.terminalvalue.mica.classfile;

import static net.terminalvalue.mica.Tests.equal;

public final class CodeAttributeTest {

    private CodeAttributeTest() {}

    // javac -g:none: Code attributes with no nested attributes.
    public static void aMethodWithNoHandlersIsTwelveBytesPlusItsCode() {
        equal(13, CodeAttribute.attributeLength(1, 0, new int[0]));
        equal(37, CodeAttribute.attributeLength(25, 0, new int[0]));
    }

    public static void everyHandlerAddsEightBytes() {
        equal(45, CodeAttribute.attributeLength(25, 1, new int[0]));
        equal(61, CodeAttribute.attributeLength(25, 3, new int[0]));
    }
}
