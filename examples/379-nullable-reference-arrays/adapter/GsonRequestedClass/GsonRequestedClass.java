import com.google.gson.*;

public final class GsonRequestedClass {
    public static boolean compatible(int selection) {
        String json = selection == 0 ? "\"abc\"" : selection == 1 || selection == 3 ? "{\"k\":1}" : "[1]";
        Class<?> requested = selection <= 2 ? JsonElement.class : selection == 3 ? JsonObject.class : JsonArray.class;
        Class<?> actual = selection == 0 ? JsonPrimitive.class : selection == 1 || selection == 3 ? JsonObject.class : JsonArray.class;
        return new Gson().fromJson(json, requested).getClass() == actual;
    }
    public static boolean syntax(int selection) {
        String json = selection < 2 ? "\"abc\"" : selection == 2 ? "{\"k\":1}" : "[1]";
        Class<?> requested = selection == 0 || selection == 3 ? JsonObject.class : JsonArray.class;
        try { new Gson().fromJson(json, requested); return false; }
        catch (JsonSyntaxException e) { return e.getClass() == JsonSyntaxException.class; }
        catch (ClassCastException e) { return false; }
    }
}
