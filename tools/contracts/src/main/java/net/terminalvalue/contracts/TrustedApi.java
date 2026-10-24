package net.terminalvalue.contracts;

import java.util.Set;

/**
 * JDK methods trusted to be pure: deterministic, and without effects beyond the objects they create. Everything
 * else in the JDK is rejected, including the clock, randomness, I/O, threads, reflection and system properties. This
 * list is the trusted base of every contract; keep it short and review additions.
 */
final class TrustedApi {

    private static final Set<String> IMMUTABLE_TYPES = Set.of(
            "java/lang/String", "java/lang/Math", "java/lang/StrictMath", "java/util/Objects",
            "java/lang/Integer", "java/lang/Long", "java/lang/Short", "java/lang/Byte",
            "java/lang/Boolean", "java/lang/Character");

    private static final Set<String> COLLECTION_TYPES = Set.of("java/util/List", "java/util/Set", "java/util/Map");

    private static final Set<String> COLLECTION_READS = Set.of(
            "of", "copyOf", "size", "isEmpty", "get", "contains", "containsAll", "containsKey", "equals", "hashCode");

    private TrustedApi() {}

    static boolean isPure(String owner, String name) {
        if (IMMUTABLE_TYPES.contains(owner)) {
            return !name.equals("random");
        }
        if (COLLECTION_TYPES.contains(owner)) {
            return COLLECTION_READS.contains(name);
        }
        return switch (owner) {
            case "java/lang/Object", "java/lang/Record" -> name.equals("<init>");
            case "java/lang/Enum" -> Set.of("<init>", "ordinal", "name", "equals", "hashCode", "compareTo", "valueOf")
                    .contains(name);
            // Constructing an exception records a stack trace, which is not part of any outcome a contract compares.
            default -> owner.startsWith("java/lang/")
                    && (owner.endsWith("Exception") || owner.endsWith("Error"))
                    && name.equals("<init>");
        };
    }
}
