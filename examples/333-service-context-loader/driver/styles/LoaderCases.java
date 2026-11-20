package styles;

public final class LoaderCases {
    public static void main(String[] args) throws Exception {
        for (int code = 0; code < 16; code++) {
            String[][] rows = World.sequence(code);
            StringBuilder line = new StringBuilder("{\"id\":").append(code).append(",\"calls\":[");
            for (int i = 0; i < rows.length; i++) {
                if (i != 0) line.append(',');
                line.append("[\"").append(String.join("\",\"", rows[i])).append("\"]");
            }
            System.out.println(line.append("]}"));
        }
    }
}
