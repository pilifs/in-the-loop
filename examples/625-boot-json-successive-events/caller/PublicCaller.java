import java.nio.charset.StandardCharsets;
import java.util.concurrent.FutureTask;
import org.springframework.boot.json.JsonWriter;

public class PublicCaller {
    public static String observe(String[] args) throws Exception {
        if (!args[0].equals("control")) throw new IllegalArgumentException(args[0]);
        var task = new FutureTask<String>(() -> {
            JsonWriter<String> writer = JsonWriter.of(members -> members.add("ok").as(value -> value));
            return new String(writer.write("a").toByteArray(), StandardCharsets.UTF_8) + "/"
                    + new String(writer.write("b").toByteArray(), StandardCharsets.UTF_8);
        });
        new Thread(task).start();
        return task.get();
    }
}
