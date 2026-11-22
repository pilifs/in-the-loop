package foundation;

import org.apache.avro.JsonProperties;
import org.apache.avro.util.internal.Accessor;
import com.fasterxml.jackson.databind.JsonNode;

/** A second installation detects whether the real superclass installed its cross-class accessor. */
public final class SchemaRegistration {
    static final class Marker extends Accessor.JsonPropertiesAccessor {
        int calls;
        protected void addProp(JsonProperties target, String name, JsonNode value) { calls++; }
    }

    public static boolean originalInstall() {
        if (JsonProperties.NULL_VALUE == null) return false;
        try {
            Accessor.setAccessor(new Marker());
            return false;
        } catch (IllegalStateException alreadyInstalled) {
            return true;
        }
    }

    public static boolean firstInstallation() {
        Marker first = new Marker();
        Accessor.setAccessor(first);
        Marker second = new Marker();
        try {
            Accessor.setAccessor(second);
            return false;
        } catch (IllegalStateException alreadyInstalled) {
            Accessor.addProp(null, "probe", null);
            return first.calls == 1 && second.calls == 0;
        }
    }

    public static boolean priorInstallation() {
        Accessor.setAccessor(new Marker());
        try {
            return JsonProperties.NULL_VALUE == null;
        } catch (ExceptionInInitializerError expected) {
            try {
                Object again = JsonProperties.NULL_VALUE;
                return false;
            } catch (NoClassDefFoundError erroneousClass) {
                return expected.getCause() instanceof IllegalStateException;
            }
        }
    }
    public static void main(String[] args) {
        boolean ok = switch (args[0]) {
            case "originalInstall" -> originalInstall();
            case "firstInstallation" -> firstInstallation();
            case "priorInstallation" -> priorInstallation();
            default -> throw new IllegalArgumentException(args[0]);
        };
        if (!ok) throw new AssertionError(args[0]);
        System.out.println("held");
    }
}
