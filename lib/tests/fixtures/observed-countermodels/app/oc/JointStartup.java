package oc;

public class JointStartup {
    static class Store {
        static int[] bytes;
        static int count;
        static Object opaque;
    }

    static class Root {
        static final int[] bytes = { 3 };
        static {
            Store.bytes = bytes;
            Store.count = 7;
            Store.opaque = new StringBuilder("registered");
        }
    }

    public static boolean shared() {
        int[] owned = Root.bytes;
        Store.bytes[0]++;
        return owned == Store.bytes && owned[0] == 4 && Store.count == 7;
    }

    public static boolean touchedFirst() {
        Store.count = 19;
        return shared();
    }

    public static boolean readsOpaque() {
        int[] owned = Root.bytes;
        return Store.opaque != null;
    }

    public static void main(String[] args) throws Exception {
        Class.forName(Root.class.getName());
        System.out.println(args.length == 0 ? shared() : touchedFirst());
    }
}
