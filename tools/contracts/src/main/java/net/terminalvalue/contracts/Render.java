package net.terminalvalue.contracts;

import java.lang.reflect.RecordComponent;
import java.util.Collection;
import java.util.StringJoiner;

/**
 * A canonical text form of values, used on both sides of the contract. It depends only on the values' structure, never
 * on {@code toString} overrides or identity hash codes, so equal behaviour renders equally on every run and JVM.
 */
final class Render {

    private Render() {}

    static String value(Object value) {
        return switch (value) {
            case null -> "null";
            case Enum<?> e -> e.name();
            case String s -> quote(s);
            case Boolean _, Number _, Character _ -> value.toString();
            case Record r -> record(r);
            case Collection<?> c -> {
                var joiner = new StringJoiner(", ", "[", "]");
                c.forEach(element -> joiner.add(value(element)));
                yield joiner.toString();
            }
            default -> "<" + value.getClass().getName() + ">";
        };
    }

    /**
     * An exception as an outcome. A NullPointerException's message is left out: the JDK writes it, and its wording
     * changes between JDK versions.
     */
    static String thrown(Throwable t) {
        String name = t.getClass().getSimpleName();
        return t instanceof NullPointerException || t.getMessage() == null
                ? "throws " + name
                : "throws " + name + "(" + quote(t.getMessage()) + ")";
    }

    private static String record(Record r) {
        var joiner = new StringJoiner(", ", r.getClass().getSimpleName() + "[", "]");
        for (RecordComponent component : r.getClass().getRecordComponents()) {
            try {
                var accessor = component.getAccessor();
                accessor.setAccessible(true);
                joiner.add(component.getName() + "=" + value(accessor.invoke(r)));
            } catch (ReflectiveOperationException e) {
                throw new IllegalStateException(e);
            }
        }
        return joiner.toString();
    }

    private static String quote(String s) {
        return '"' + s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n") + '"';
    }
}
