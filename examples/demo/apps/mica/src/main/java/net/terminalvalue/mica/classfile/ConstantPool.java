package net.terminalvalue.mica.classfile;

/**
 * The constant pool (JVMS §4.4). Entries are numbered from 1, and a {@code CONSTANT_Long} or
 * {@code CONSTANT_Double} entry takes two numbers: the one after it is unusable. The specification says of this
 * that, in retrospect, making 8-byte constants take two constant pool entries was a poor choice; every class file
 * reader lives with it.
 */
public final class ConstantPool {

    public static final int CONSTANT_LONG = 5;
    public static final int CONSTANT_DOUBLE = 6;

    private ConstantPool() {}

    /**
     * The constant pool index of the entry at position {@code entry} (counting from 0) in a pool whose entries have
     * the given tags, in order.
     */
    public static int indexOf(byte[] tags, int entry) {
        int index = 1;
        for (int i = 0; i < entry; i++) {
            index += tags[i] == CONSTANT_LONG || tags[i] == CONSTANT_DOUBLE ? 2 : 1;
        }
        return index;
    }
}
