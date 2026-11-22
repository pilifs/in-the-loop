package foundation;

import java.lang.reflect.Field;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.HashSet;
import java.util.HexFormat;
import java.util.Set;

/** The two consecutive assignments and insertion in both original Avro Schema initializers. */
public final class ReservedNames {
    private static final Set<String> SCHEMA_RESERVED = new HashSet<>(
        Arrays.asList("doc", "fields", "items", "name", "namespace", "size", "symbols", "values", "type", "aliases"));
    private static final Set<String> ENUM_RESERVED = new HashSet<>(SCHEMA_RESERVED);
    static { ENUM_RESERVED.add("default"); }

    static boolean contents(Set<?> schema, Set<?> enumeration) {
        if (schema == enumeration || schema.size() != 10 || enumeration.size() != 11
                || schema.contains("default") || !enumeration.contains("default")) return false;
        for (String field : new String[]{"aliases", "doc", "fields", "items", "name", "namespace", "size", "symbols", "type", "values"})
            if (!schema.contains(field) || !enumeration.contains(field)) return false;
        return true;
    }

    public static boolean reserved() { return contents(SCHEMA_RESERVED, ENUM_RESERVED); }
    public static boolean defaultLeaks() { return SCHEMA_RESERVED.contains("default"); }

    static Set<?> field(Class<?> cls, String name) throws ReflectiveOperationException {
        Field field = cls.getDeclaredField(name);
        field.setAccessible(true);
        return (Set<?>) field.get(null);
    }

    public static void main(String[] args) throws Exception {
        Class<?> schema = Class.forName("org.apache.avro.Schema");
        if (!contents(field(schema, "SCHEMA_RESERVED"), field(schema, "ENUM_RESERVED")))
            throw new AssertionError("original Schema reserved names differ");
        try (var in = schema.getResourceAsStream("Schema.class")) {
            System.out.println(HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(in.readAllBytes())));
        }
    }
}
