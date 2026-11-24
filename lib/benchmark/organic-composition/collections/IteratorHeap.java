import com.sun.jdi.ArrayReference;
import com.sun.jdi.Field;
import com.sun.jdi.ObjectReference;
import com.sun.jdi.Value;
import com.sun.jdi.VirtualMachine;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

/** A stable numbering of the finite entry heap. Keep even the unlinked queue node observable. */
final class IteratorHeap {
    private final List<ObjectReference> objects = new ArrayList<>();
    private final Map<ObjectReference, String> names = new LinkedHashMap<>();
    private final Map<String, ValueSlot> fields = new TreeMap<>();
    private final Map<String, String> roots = new TreeMap<>();
    private final VirtualMachine vm;
    private boolean sealed;

    private record ValueSlot(ObjectReference owner, Field field) {}

    IteratorHeap(VirtualMachine vm, Map<String, ObjectReference> orderedRoots) {
        this.vm = vm;
        orderedRoots.forEach((name, object) -> roots.put("root/" + name, label(object)));
    }

    String label(Value value) {
        if (value == null) return "null";
        if (!(value instanceof ObjectReference object)) return value.type().signature() + ":" + value;
        String known = names.get(object);
        if (known != null) return known;
        if (sealed) throw new IllegalStateException("new reference outside the admitted heap: " + value.type().name());
        object.disableCollection();
        String name = "@" + objects.size();
        objects.add(object);
        names.put(object, name);
        return name;
    }

    static String member(Field field) {
        return field.declaringType().name() + "#" + field.name() + ":" + field.signature();
    }

    Map<String, String> snapshot() {
        Map<String, String> state = new TreeMap<>(roots);
        // Breadth-first, with fields in declaration-identity order and array entries in index order.
        for (int index = 0; index < objects.size(); index++) {
            ObjectReference object = objects.get(index);
            String prefix = "@" + index + "/";
            state.put(prefix + "type", object.referenceType().name());
            if (object instanceof ArrayReference array) {
                List<Value> entries = array.getValues();
                for (int i = 0; i < entries.size(); i++) state.put(prefix + i, label(entries.get(i)));
            } else {
                List<Field> instance = new ArrayList<>(object.referenceType().allFields());
                instance.removeIf(Field::isStatic);
                instance.sort(Comparator.comparing(IteratorHeap::member));
                Map<Field, Value> values = object.getValues(instance);
                for (Field field : instance) {
                    String key = prefix + member(field);
                    fields.put(key, new ValueSlot(object, field));
                    state.put(key, label(values.get(field)));
                }
            }
        }
        sealed = true;
        return state;
    }

    void apply(Map<String, String> writes) throws Exception {
        for (var edit : writes.entrySet()) {
            ValueSlot slot = fields.get(edit.getKey());
            if (slot == null || slot.field().isFinal()) throw new IllegalArgumentException("unwritable slot " + edit.getKey());
            String encoded = edit.getValue();
            Value value;
            if (encoded.equals("null")) value = null;
            else if (encoded.startsWith("@")) value = objects.get(Integer.parseInt(encoded.substring(1)));
            else if (encoded.startsWith("I:")) value = vm.mirrorOf(Integer.parseInt(encoded.substring(2)));
            else throw new IllegalArgumentException("unsupported effect value " + encoded);
            slot.owner().setValue(slot.field(), value);
        }
    }
}
