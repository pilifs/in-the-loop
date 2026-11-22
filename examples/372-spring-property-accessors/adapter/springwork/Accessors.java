package springwork;

import org.springframework.core.convert.Property;

public final class Accessors {
    public record Budget(int budget) {}
    public record Issue(String issue) {}
    public record Widget(String getWidget) {}
    public record Plain(String name) {}
    public static final class Bean { private String name; public String getName() { return name; } }
    public record Extra(String widgetId) { public String getWidget() { return widgetId; } }

    public static String method(int i) {
        return switch (i) { case 0 -> "budget"; case 1 -> "issue"; case 2,5 -> "getWidget"; case 3 -> "name"; default -> "getName"; };
    }
    public static Class<?> type(int i) {
        return switch (i) { case 0 -> Budget.class; case 1 -> Issue.class; case 2 -> Widget.class;
            case 3 -> Plain.class; case 4 -> Bean.class; default -> Extra.class; };
    }
    public static String name(int i) throws Exception {
        Class<?> type = type(i);
        return new Property(type, type.getMethod(method(i)), null).getName();
    }
    public static int components(int code) throws Exception { return method(code).equals(name(code)) ? 1 : 0; }
    public static int getters(int code) throws Exception { return (code == 2 ? "widget" : "name").equals(name(3 + code)) ? 1 : 0; }
}
