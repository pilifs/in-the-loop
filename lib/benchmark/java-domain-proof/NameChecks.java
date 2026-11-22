package campaign;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import org.apache.avro.Schema;
import org.apache.avro.SchemaParseException;

/** Compare the bytecode after the name-policy lookup with independent name and exception observations. */
public final class NameChecks {
    // Read only by the debugger while a frozen public entry is on the stack.
    public static int selector;
    static String name(int code) {
        return switch (code) {
            case 0 -> "MyRecord"; case 1 -> "field"; case 2 -> "E"; case 3 -> "Other";
            case 4 -> "A"; case 5 -> "B"; case 6 -> "writer"; case 7 -> "reader";
            case 8 -> "RecordA"; case 9 -> "Element"; case 10 -> "value"; case 11 -> "marker";
            case 12 -> "fieldA"; case 13 -> "_A0"; case 14 -> null; case 15 -> "";
            case 16 -> "0start"; default -> "bad-name";
        };
    }

    static boolean accepts(String name, Object policy) {
        try {
            if (NameSuffix.validateName(name, policy) != name) throw new AssertionError("name identity");
            return true;
        } catch (SchemaParseException rejected) {
            return false;
        }
    }

    public static int names(int code) {
        return accepts(name(code), NameSuffix.defaultPolicy()) == (code < 14) ? 1 : 0;
    }

    static boolean letter(char c) { return c >= 'A' && c <= 'Z' || c >= 'a' && c <= 'z'; }

    public static int twoAscii(char first, char second) {
        String name = new String(new char[]{first, second});
        boolean expected = (letter(first) || first == '_')
                && (letter(second) || second == '_' || second >= '0' && second <= '9');
        return accepts(name, NameSuffix.defaultPolicy()) == expected ? 1 : 0;
    }

    static boolean originalAccepts(Method original, String name) throws Exception {
        try {
            if (original.invoke(null, name) != name) throw new AssertionError("original name identity");
            return true;
        } catch (InvocationTargetException thrown) {
            if (thrown.getCause().getClass() == SchemaParseException.class) return false;
            throw thrown;
        }
    }

    public static void main(String[] args) throws Exception {
        boolean legacy = args[0].equals("364");
        Class<?> adapter = Class.forName(legacy ? "campaign.EnumReader" : "campaign.DefaultReader");
        String[] entries = legacy ? new String[]{"renamed", "preserved"} : new String[]{"union", "direct"};
        for (String entry : entries) {
            for (selector = 0; selector < 4; selector++) {
                int value = (int) adapter.getMethod(entry, int.class).invoke(null, selector);
                if (value != (entry.equals(entries[0]) && args[1].equals("parent") ? 0 : 1))
                    throw new AssertionError("public reader " + entry + " " + selector);
                if (args.length == 3) System.out.println("CALL\t" + entry + "\t" + selector + "\t" + value);
            }
        }
        if (args.length == 3) return;
        var field = Schema.class.getDeclaredField(legacy ? "validateNames" : "VALIDATE_NAMES");
        field.setAccessible(true);
        @SuppressWarnings("unchecked")
        ThreadLocal<Object> local = (ThreadLocal<Object>) field.get(null);
        Method original = Schema.class.getDeclaredMethod("validateName", String.class);
        original.setAccessible(true);
        Object policy = NameSuffix.defaultPolicy();
        if (local.get() != policy) throw new AssertionError("public reader used a different policy");
        Object permissive = legacy ? Boolean.FALSE : Class.forName("org.apache.avro.NameValidator").getField("NO_VALIDATION").get(null);
        if (policy == permissive) throw new AssertionError("indistinguishable name policies");
        int valid = 0;
        Method publicUtf = legacy ? null : Class.forName("campaign.UtfNameChecks").getMethod("names", int.class);
        try {
            for (int code = 0; code < 18; code++) {
                String name = name(code);
                boolean accepted = originalAccepts(original, name);
                if (accepted != (code < 14) || names(code) != 1
                        || publicUtf != null && (int) publicUtf.invoke(null, code) != 1)
                    throw new AssertionError("name selector " + code);
                if (accepted) valid++;
            }
            for (char first = 0; first < 128; first++) for (char second = 0; second < 128; second++) {
                String name = new String(new char[]{first, second});
                if (originalAccepts(original, name) != accepts(name, policy) || twoAscii(first, second) != 1)
                    throw new AssertionError("ASCII pair " + (int) first + "," + (int) second);
            }
            local.set(permissive);
            for (int code = 14; code < 18; code++) {
                if (!originalAccepts(original, name(code)) || !accepts(name(code), permissive))
                    throw new AssertionError("changed policy did not change rejection");
            }
            local.remove();
            if (local.get() != policy || originalAccepts(original, "bad-name"))
                throw new AssertionError("supplier did not restore the original policy");
        } finally {
            local.set(policy);
        }
        System.out.println("publicCalls=8 names=18 accepted=" + valid
                + " rejected=" + (18 - valid) + " asciiPairs=16384 overrides=4 publicUtf=" + (legacy ? 0 : 18)
                + " policy=" + policy.getClass().getName());
    }
}
