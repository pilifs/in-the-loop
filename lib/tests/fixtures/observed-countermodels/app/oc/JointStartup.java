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

    static class Carrier {
        Object registered;
        int marker;

        Carrier(boolean fail, Object registered) {
            if (fail) throw new IllegalArgumentException();
            this.registered = registered;
            this.marker = 5;
        }
    }

    public static boolean carried(boolean fail) {
        try {
            Carrier c = new Carrier(fail, Store.opaque);
            c.registered = null;
            return !fail && c.marker == 5 && c.registered == null;
        } catch (IllegalArgumentException expected) {
            return fail;
        }
    }

    public static boolean inspectsCarried() {
        return new Carrier(false, Store.opaque).registered != null;
    }

    public static void main(String[] args) throws Exception {
        Class.forName(Root.class.getName());
        if (args.length > 0 && args[0].equals("carry")) {
            System.out.println(carried(false) && carried(true) && inspectsCarried());
        } else {
            System.out.println(args.length == 0 ? shared() : touchedFirst());
        }
    }
}
