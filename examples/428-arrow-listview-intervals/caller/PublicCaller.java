import java.util.ArrayList;
import java.util.List;
import org.apache.arrow.memory.RootAllocator;
import org.apache.arrow.vector.SmallIntVector;
import org.apache.arrow.vector.complex.ListViewVector;
import org.apache.arrow.vector.types.pojo.*;

public class PublicCaller {
    static void populate(ListViewVector vector, int[] values, boolean two) {
        vector.allocateNew();
        vector.initializeChildrenFromFields(List.of(new Field("numbers", FieldType.nullable(new ArrowType.Int(16, true)), null)));
        var child = (SmallIntVector) vector.getDataVector();
        child.allocateNew(values.length);
        for (int i = 0; i < values.length; i++) child.set(i, values[i]);
        child.setValueCount(values.length);
        vector.setOffset(0, 0);
        vector.setSize(0, two ? 3 : 2);
        vector.setValidity(0, 1);
        if (two) {
            vector.setOffset(1, 3);
            vector.setSize(1, 2);
            vector.setValidity(1, 1);
        }
        vector.setValueCount(two ? 2 : 1);
    }
    public static String observe(String[] args) {
        try (var allocator = new RootAllocator(1 << 20);
             var v = ListViewVector.empty("v", allocator);
             var other = ListViewVector.empty("other", allocator)) {
            populate(v, new int[]{10,20,30,40,50}, true);
            if (args[0].equals("hash")) {
                populate(other, new int[]{40,50}, false);
                return "objects=" + new ArrayList<>(v.getObject(1)) + "/" + new ArrayList<>(other.getObject(0))
                        + " equalHash=" + (v.hashCode(1) == other.hashCode(0))
                        + " hashes=" + v.hashCode(1) + "/" + other.hashCode(0);
            }
            int i = args[0].equals("zero") ? 0 : 1;
            int start = v.getElementStartIndex(i), end = v.getElementEndIndex(i);
            var values = new ArrayList<Short>();
            var child = (SmallIntVector) v.getDataVector();
            for (int j = start; j < end; j++) values.add(child.get(j));
            return start + ".." + end + " child=" + values + " object=" + new ArrayList<>(v.getObject(i));
        }
    }
}
