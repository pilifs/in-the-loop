import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Map;
import org.apache.iceberg.*;
import org.apache.iceberg.data.*;
import org.apache.iceberg.encryption.EncryptedFiles;
import org.apache.iceberg.hadoop.HadoopTables;
import org.apache.iceberg.types.Types;

public class PublicCaller {
    static final Schema SCHEMA = new Schema(Types.NestedField.required(1,"id",Types.IntegerType.get()),
            Types.NestedField.required(2,"key",Types.BinaryType.get()));
    static ByteBuffer bytes(String s) { return ByteBuffer.wrap(s.getBytes(StandardCharsets.US_ASCII)); }
    static String copy() {
        var inner = GenericRecord.create(SCHEMA.select("key"));
        var data = bytes("XABY");
        data.position(1).limit(3);
        inner.setField("key",data);
        var outer = GenericRecord.create(new Schema(Types.NestedField.required(3,"inner",inner.struct())));
        outer.setField("inner",inner);
        var saved=outer.copy();
        data.put(1,(byte)'Z');
        var nested=(GenericRecord)saved.getField("inner");
        var view=((ByteBuffer)nested.getField("key")).duplicate();
        return StandardCharsets.US_ASCII.decode(view) + " sourcePosition=" + data.position();
    }
    public static String observe(String[] args) throws Exception {
        if (args[0].equals("copy")) return copy();
        var path=Path.of("table").toAbsolutePath();
        var spec=PartitionSpec.unpartitioned();
        var table=new HadoopTables().create(SCHEMA,spec,Map.of("format-version","2"),path.toUri().toString());
        var keys=SCHEMA.select("key");
        var factory=new GenericAppenderFactory(SCHEMA,spec,new int[]{2},keys,null);
        var data=factory.newDataWriter(EncryptedFiles.plainAsEncryptedOutput(
                table.io().newOutputFile(path.resolve("values.parquet").toString())),FileFormat.PARQUET,null);
        try (data) {
            for (int i=0; i<4; i++) {
                var row=GenericRecord.create(SCHEMA);
                row.setField("id",200+i); row.setField("key",bytes("ABCD".substring(i,i+1)));
                data.write(row);
            }
        }
        table.newAppend().appendFile(data.toDataFile()).commit();
        if (args[0].equals("delete")) {
            var deletes=factory.newEqDeleteWriter(EncryptedFiles.plainAsEncryptedOutput(
                    table.io().newOutputFile(path.resolve("deletes.parquet").toString())),FileFormat.PARQUET,null);
            try (deletes) {
                for (String key : new String[]{"A","B","C"}) {
                    var row=GenericRecord.create(keys);
                    row.setField("key",bytes(key)); deletes.write(row);
                }
            }
            table.newRowDelta().addDeletes(deletes.toDeleteFile()).commit();
        }
        var ids=new ArrayList<Integer>();
        try (var rows=IcebergGenerics.read(table).select("id").build()) {
            for (var row : rows) ids.add((Integer)row.getField("id"));
        }
        ids.sort(null);
        return ids.toString();
    }
}
