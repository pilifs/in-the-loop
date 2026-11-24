import java.util.ArrayList;
import java.util.List;
import com.esotericsoftware.kryo.Kryo;
import com.esotericsoftware.kryo.io.Input;
import com.esotericsoftware.kryo.io.Output;

public class UpgradeProbe {
    enum Color { RED, BLUE }
    private static Kryo codec() {
        Kryo kryo = new Kryo();
        kryo.setRegistrationRequired(false);
        return kryo;
    }
    public static String observe(String[] args) {
        boolean abstractToken = args[0].equals("abstract");
        List<Class<?>> tokens = new ArrayList<>();
        tokens.add(void.class); tokens.add(ArrayList.class); tokens.add(Color.class);
        if (abstractToken) tokens.add(Enum.class);
        tokens.add(String.class);
        Kryo writer = codec();
        Output out = new Output(128, 1024);
        int written = 0;
        for (Class<?> token : tokens) {
            try { writer.writeObject(out, token); }
            catch (IllegalArgumentException e) { return "write/" + written + "/" + token.getName() + "/" + e.getClass().getSimpleName(); }
            written++;
        }
        byte[] bytes = out.toBytes();
        Input input = new Input(bytes);
        Kryo reader = codec();
        StringBuilder ids = new StringBuilder();
        for (Class<?> token : tokens) {
            Class<?> returned = reader.readObject(input, Class.class);
            if (returned != token) throw new AssertionError("class identity differs at " + token.getName());
            if (ids.length() > 0) ids.append(',');
            ids.append(returned.getName());
        }
        return "read/" + ids + "/fully-consumed=" + (input.position() == bytes.length);
    }
}
