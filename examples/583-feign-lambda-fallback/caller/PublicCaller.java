import app.FallbackApplication;

public class PublicCaller {
    public static String observe(String[] args) throws Exception {
        return FallbackApplication.exercise(args[0]);
    }
}
