package springwork;
public final class FluentNamesReplay {
    public static void main(String[] args) {
        int value = RoleChecks.fluentNames(1);
        System.out.print(value);
        String separator = System.lineSeparator();
        for (int i = 0; i < separator.length(); i++) {
            System.out.print(" ");
            System.out.print((int) separator.charAt(i));
        }
        System.out.print("\n");
    }
}
