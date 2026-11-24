import com.sun.tools.classfile.ClassFile;
import com.sun.tools.classfile.Code_attribute;
import com.sun.tools.classfile.ConstantPool.CONSTANT_Methodref_info;
import java.io.ByteArrayInputStream;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.HexFormat;
import org.apache.commons.lang3.ArrayUtils;

/** Report the loaded methods and independently check all cells through a second reference. */
public final class ReverseRelease {
    private static final int[] BOUNDS = {Integer.MIN_VALUE, -2, -1, 0, 1, 2, 3, 4, 5, 6, Integer.MAX_VALUE};

    private static ClassFile loaded(Class<?> type) throws Exception {
        byte[] bytes;
        try (var stream = type.getResourceAsStream(type.getSimpleName() + ".class")) {
            bytes = stream.readAllBytes();
        }
        var file = ClassFile.read(new ByteArrayInputStream(bytes));
        if (!file.getName().equals(type.getName().replace('.', '/'))) throw new AssertionError(type);
        System.out.println(type.getSimpleName() + " " + HexFormat.of().formatHex(
            MessageDigest.getInstance("SHA-256").digest(bytes)));
        return file;
    }

    private static Code_attribute method(ClassFile file, String name, String descriptor) throws Exception {
        for (var method : file.methods) {
            if (!name.equals(method.getName(file.constant_pool)) ||
                !descriptor.equals(method.descriptor.getValue(file.constant_pool))) continue;
            var code = (Code_attribute) method.attributes.get("Code");
            if (method.access_flags.flags != 9 || code.exception_table_length != 0) throw new AssertionError(name);
            System.out.println(name + " " + HexFormat.of().formatHex(code.code));
            return code;
        }
        throw new AssertionError(name + descriptor);
    }

    private static void binding(ClassFile file, Code_attribute body, int pc, String name) throws Exception {
        if (body.getUnsignedByte(pc) != 0xb8) throw new AssertionError("expected invokestatic at " + pc);
        var ref = (CONSTANT_Methodref_info) file.constant_pool.get(body.getUnsignedShort(pc + 1));
        var method = ref.getNameAndTypeInfo();
        if (!ref.getClassName().equals("java/lang/Math") || !name.equals(method.getName()) ||
            !method.getType().equals("(II)I")) throw new AssertionError("callee at " + pc);
        System.out.println("call" + pc + " " + ref.getClassName() + "." + method.getName() + method.getType());
    }

    public static void main(String[] args) throws Exception {
        var owner = loaded(ArrayUtils.class);
        var math = loaded(Math.class);
        var body = method(owner, "reverse", "([III)V");
        binding(owner, body, 7, "max");
        binding(owner, body, 14, "min");
        method(math, "max", "(II)I");
        method(math, "min", "(II)I");

        int normal = 0, exceptional = 0, valid = 0, empty = 0, single = 0, nulls = 0;
        for (int n = -1; n <= 5; n++) {
            int count = n < 0 ? 1 : (int) Math.pow(3, n);
            for (int pattern = 0; pattern < count; pattern++) {
                int[] before = n < 0 ? null : new int[n];
                for (int k = 0, bits = pattern; k < n; k++, bits /= 3) before[k] = bits % 3 - 1;
                for (int start : BOUNDS) for (int end : BOUNDS) {
                    int[] target = n < 0 ? null : before.clone();
                    int[] alias = target;
                    boolean shouldThrow = n >= 0 && end == Integer.MIN_VALUE && start < Integer.MAX_VALUE;
                    try {
                        ArrayUtils.reverse(target, start, end);
                    } catch (ArrayIndexOutOfBoundsException ex) {
                        if (ex.getClass() != ArrayIndexOutOfBoundsException.class ||
                            !shouldThrow || !Arrays.equals(before, alias)) throw new AssertionError(ex);
                        exceptional++;
                        continue;
                    }
                    if (shouldThrow) throw new AssertionError("missing exception");
                    normal++;
                    if (n < 0) { nulls++; continue; }
                    int lo = Math.max(0, start), hi = Math.min(n, end);
                    for (int k = 0; k < n; k++) {
                        int source = lo <= k && k < hi ? lo + (hi - 1 - k) : k;
                        if (alias[k] != before[source]) throw new AssertionError("cell " + k);
                    }
                    if (0 <= start && start <= end && end <= n) {
                        valid++;
                        if (start == end) empty++;
                        if (end - start == 1) single++;
                    }
                }
            }
        }
        System.out.printf("grid %d %d %d %d %d %d%n", normal, exceptional, valid, empty, single, nulls);
        int[] a = {};
        try {
            ArrayUtils.reverse(a, 0, Integer.MIN_VALUE);
            throw new AssertionError("missing empty-array exception");
        } catch (ArrayIndexOutOfBoundsException ex) {
            System.out.println("witness " + ex + " heap=" + Arrays.toString(a));
        }
        ArrayUtils.reverse(a, Integer.MAX_VALUE, Integer.MIN_VALUE);
        ArrayUtils.reverse((int[]) null, 0, Integer.MIN_VALUE);
        System.out.println("controls MAX,MIN returned with [] and null,0,MIN returned");
    }
}
