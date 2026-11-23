package springwork;

public final class MetadataNames {
    public static void main(String[] args) throws Exception {
        for (int i = 0; i < 6; i++) {
            int result = i < 3 ? Accessors.components(i) : Accessors.getters(i - 3);
            System.out.println(i + "\t" + Accessors.name(i) + "\t" + result);
        }
    }
}
