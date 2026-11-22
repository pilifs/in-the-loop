package campaign;
import java.util.List;
import org.apache.avro.generic.GenericRecord;
import static org.intheloop.controls.Grid.*;

public final class Cases {
    static Object outcome(int code, boolean union, boolean required, boolean fast, boolean json) throws Exception {
        try {
            GenericRecord r = DefaultReader.read(code, union, required, fast, json);
            Object value = r.get("fieldA");
            return fields("size", value instanceof List ? ((List<?>) value).size() : -1,
                          "marker", code == 0 ? null : r.get("marker"));
        } catch (org.apache.avro.AvroRuntimeException failure) {
            return failure.getClass().getName();
        }
    }
    public static void main(String[] args) throws Exception {
        for (int code=0; code<4; code++) {
            if (args.length == 1 && args[0].equals("--controls")) {
                for (boolean fast : new boolean[]{false,true}) for (boolean json : new boolean[]{false,true}) {
                    System.out.println(code + " " + fast + " " + json + " "
                        + outcome(code, true, false, fast, json) + " " + outcome(code, false, false, fast, json)
                        + " " + outcome(code, true, true, fast, json));
                }
            } else {
                row(code, fields("marker", code == 0 ? null : DefaultReader.marker(code)),
                    fields("union", outcome(code,true,false,true,false), "direct", outcome(code,false,false,true,false)),
                    fields("union", DefaultReader.union(code), "direct", DefaultReader.direct(code)));
            }
        }
    }
}
