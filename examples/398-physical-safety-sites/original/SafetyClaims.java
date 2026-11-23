public final class SafetyClaims {
    public static int dividing(int value) { return SafetySites.run(0,value); }
    public static int indexing(int value) { return SafetySites.run(1,value); }
    public static int guarded() { return SafetySites.run(3,0); }
    public static int summing() { return SafetySites.run(2,0); }
    public static boolean caught(int value) { return value != 0 || dividing(value) == -10; }
    public static boolean sum() { return summing() == 21; }
}
