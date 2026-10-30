package net.terminalvalue.contracts;

import java.lang.reflect.Constructor;
import java.lang.reflect.RecordComponent;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/**
 * Enumerates every value of a type whose values are finite: booleans, enums, records of finite types, and sealed
 * hierarchies of those. Such a type is an algebraic data type, so a method whose parameters all have such types has
 * finitely many inputs, and running it on each of them decides its behaviour completely.
 */
final class Domains {

    /** A parameter type with infinitely many values, such as {@code long} or {@code String}. */
    static final class UnboundedException extends Exception {
        UnboundedException(String message) {
            super(message);
        }
    }

    static final int MAX_CASES = 100_000;

    private Domains() {}

    /**
     * Every value of {@code type}. A top-level reference parameter also takes {@code null}, because callers can pass
     * it. Record components do not, which this POC accepts as a simplification.
     */
    static List<Object> values(Class<?> type, boolean nullable) throws UnboundedException {
        var values = enumerate(type, new HashSet<>());
        if (nullable && !type.isPrimitive()) {
            values.add(null);
        }
        return values;
    }

    private static List<Object> enumerate(Class<?> type, Set<Class<?>> visiting) throws UnboundedException {
        if (!visiting.add(type)) {
            throw new UnboundedException(type.getName() + " is recursive");
        }
        try {
            if (type == boolean.class || type == Boolean.class) {
                return new ArrayList<>(List.of(false, true));
            }
            if (type.isEnum()) {
                return new ArrayList<>(Arrays.asList(type.getEnumConstants()));
            }
            if (type.isRecord()) {
                return records(type, visiting);
            }
            if (type.isSealed()) {
                var values = new ArrayList<>();
                for (Class<?> sub : type.getPermittedSubclasses()) {
                    values.addAll(enumerate(sub, visiting));
                }
                return values;
            }
            throw new UnboundedException(type.getName() + " has unboundedly many values");
        } finally {
            visiting.remove(type);
        }
    }

    private static List<Object> records(Class<?> type, Set<Class<?>> visiting) throws UnboundedException {
        RecordComponent[] components = type.getRecordComponents();
        List<List<Object>> domains = new ArrayList<>();
        for (RecordComponent component : components) {
            domains.add(enumerate(component.getType(), visiting));
        }
        Constructor<?> constructor;
        try {
            constructor = type.getDeclaredConstructor(
                    Arrays.stream(components).map(RecordComponent::getType).toArray(Class<?>[]::new));
            constructor.setAccessible(true);
        } catch (NoSuchMethodException e) {
            throw new IllegalStateException("record without canonical constructor: " + type.getName(), e);
        }
        var values = new ArrayList<>();
        for (List<Object> args : product(domains)) {
            try {
                values.add(constructor.newInstance(args.toArray()));
            } catch (ReflectiveOperationException e) {
                // A compact constructor that rejects these components: the value does not exist.
            }
        }
        return values;
    }

    /** The cartesian product, in order: the last list varies fastest. */
    static List<List<Object>> product(List<List<Object>> domains) throws UnboundedException {
        List<List<Object>> result = new ArrayList<>();
        result.add(List.of());
        for (List<Object> domain : domains) {
            if ((long) result.size() * domain.size() > MAX_CASES) {
                throw new UnboundedException("more than " + MAX_CASES + " cases");
            }
            List<List<Object>> next = new ArrayList<>();
            for (List<Object> prefix : result) {
                for (Object value : domain) {
                    var extended = new ArrayList<>(prefix);
                    extended.add(value);
                    next.add(extended);
                }
            }
            result = next;
        }
        return result;
    }
}
