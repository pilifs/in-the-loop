import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import com.esotericsoftware.kryo.Kryo;
import com.esotericsoftware.kryo.io.Input;
import com.esotericsoftware.kryo.io.Output;

public class StreamPosition {
    public static void main(String[] args) {
        List<Class<?>> types = new ArrayList<>(Arrays.asList(void.class,ArrayList.class,UpgradeProbe.Color.class));
        if (args[0].equals("abstract")) types.add(Enum.class);
        types.add(String.class);
        Kryo writer = new Kryo(); writer.setRegistrationRequired(false);
        Output out = new Output(128,1024);
        int completeBytes = 0, completeTokens = 0;
        for (Class<?> type : types) {
            try {
                writer.writeObject(out,type);
                completeBytes = out.position();
                completeTokens++;
                System.out.println("write " + type.getName() + " " + completeBytes);
            } catch (IllegalArgumentException e) {
                System.out.println("failure " + type.getName() + " " + e.getClass().getSimpleName());
                break;
            }
        }
        byte[] bytes = out.toBytes();
        Kryo reader = new Kryo(); reader.setRegistrationRequired(false);
        Input input = new Input(Arrays.copyOf(bytes,completeBytes));
        for (int i=0;i<completeTokens;i++) {
            Class<?> value = reader.readObject(input,Class.class);
            if (value != types.get(i)) throw new AssertionError("token identity differs");
            System.out.println("read " + value.getName() + " " + input.position());
        }
        if (input.position() != completeBytes) throw new AssertionError("unconsumed complete token");
        System.out.println("end " + bytes.length + " " + completeBytes);
    }
}
