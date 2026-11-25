public final class AfterStartup {
    public static void main(String[] args) throws Exception {
        Class<?> c = Class.forName("com.google.protobuf.CodedOutputStream", true, AfterStartup.class.getClassLoader());
        if (!java.nio.file.Path.of(c.getProtectionDomain().getCodeSource().getLocation().toURI()).toRealPath().equals(java.nio.file.Path.of(args[0]).toRealPath())) throw new AssertionError();
        for (int i = 1; i < args.length; i++) {
            long n = Long.parseLong(args[i]);
            System.out.println(n+" "+PublishedWidths.roundTrip((int)n)+" "+PublishedWidths.size32((int)n)+" "+PublishedWidths.size64(n)+" "+PublishedWidths.wrong64(n));
        }
    }
}
