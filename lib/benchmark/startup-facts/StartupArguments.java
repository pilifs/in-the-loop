/** Expose the exact UTF-16 argv of the child without relying on its console encoding. */
public class StartupArguments {
    public static String units(String[] args) {
        StringBuilder result = new StringBuilder();
        for (String arg : args) {
            result.append(arg.length()).append(':');
            for (int i = 0; i < arg.length(); i++) result.append((int)arg.charAt(i)).append(',');
            result.append('|');
        }
        return result.toString();
    }
    public static void main(String[] args) { System.out.println(units(args)); }
}
