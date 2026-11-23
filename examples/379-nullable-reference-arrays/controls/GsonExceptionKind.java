import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

/** Observe the exact exception on each of the four incompatible public calls. */
public final class GsonExceptionKind {
    public static boolean casts(int selection) {
        String json = selection < 2 ? "\"abc\"" : selection == 2 ? "{\"k\":1}" : "[1]";
        Class<?> requested = selection == 0 || selection == 3 ? JsonObject.class : JsonArray.class;
        try {
            new Gson().fromJson(json, requested);
            return false;
        } catch (RuntimeException thrown) {
            return thrown.getClass() == ClassCastException.class;
        }
    }
}
