package net.terminalvalue.mica.classfile;

/**
 * The layout of a {@code Code} attribute (JVMS §4.7.3): {@code max_stack} and {@code max_locals} (two bytes each),
 * {@code code_length} (four) and the code, {@code exception_table_length} (two) and eight bytes per entry, then
 * {@code attributes_count} (two) and the nested attributes, each of which is a six-byte header, the name index and
 * the length, followed by its {@code attribute_length} bytes of information.
 */
public final class CodeAttribute {

    private CodeAttribute() {}

    /**
     * The {@code attribute_length} of a {@code Code} attribute with {@code codeLength} bytes of code,
     * {@code exceptionTableLength} exception table entries, and nested attributes of the given
     * {@code attribute_length}s: everything after the attribute's own six-byte header.
     */
    public static int attributeLength(int codeLength, int exceptionTableLength, int[] nestedAttributeLength) {
        int nested = 0;
        for (int i = 0; i < nestedAttributeLength.length; i++) {
            nested += 6 + nestedAttributeLength[i];
        }
        return 2 + 2 + 4 + codeLength + 2 + 8 * exceptionTableLength + 2 + nested;
    }
}
