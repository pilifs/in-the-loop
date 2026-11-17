package lc;

/** The entry points: each property the tests state of them is false on a JVM, which main shows. */
public final class M {
    private M() {}

    /** Base.SEEN: the call in Base's initializer reads LIMIT before it is written. */
    public static int seen() {
        return Base.SEEN;
    }

    /** Derived.limit() once Base is initialized: 7. */
    public static int derivedLimit() {
        return Derived.limit();
    }

    /** Holder.SEEN, the same through a class that is no subclass. */
    public static int heldSeen() {
        return Holder.SEEN;
    }

    /** Appends to the builder, then asks the getter for its length. */
    public static int appendThenLogged() {
        Logged.LOG.append("x");
        return Logged.logged();
    }

    public static int appendThenLoggedThroughLambda() {
        Logged.LOG.append("x");
        return Logged.loggedThroughLambda();
    }

    public static int setThenBoxed(int v) {
        Boxed.BOX[0] = v;
        return Boxed.boxed();
    }

    public static int addThenItems() {
        Listed.ITEMS.add("x");
        return Listed.items();
    }

    public static int setThenReflected(int v) throws ReflectiveOperationException {
        Reflected.level = v;
        return Reflected.reflected();
    }

    /** Writes the setting, then asks Own, which is initialized only now. */
    public static int setThenOwn(int v) {
        Settings.value = v;
        return Own.limit();
    }

    /** Sets a Turkish default, then asks Lowered, which is initialized only now. */
    public static int turkishThenLowered() {
        java.util.Locale.setDefault(java.util.Locale.forLanguageTag("tr"));
        return Lowered.lowered();
    }

    /** Writes Table's array, then asks Copied, which is initialized only now. */
    public static int setThenCopied(int v) {
        Table.T[0] = v;
        return Copied.first();
    }

    /** Writes Cloned's array, then asks for a copy's first cell. */
    public static int setThenCloned(int v) {
        Cloned.T[0] = v;
        return Cloned.cloned();
    }

    public static int setThenCopiedOf(int v) {
        Cloned.T[0] = v;
        return Cloned.copiedOf();
    }

    /** Writes Cloned's key, then asks whether it is {0}: 1 if so. */
    public static int setThenZeroKey(int v) {
        Cloned.KEY[0] = (byte) v;
        return Cloned.zeroKey() ? 1 : 0;
    }

    public static int pinged() {
        return Mutual.ping(0);
    }

    public static void main(String[] args) throws Exception {
        StringBuilder out = new StringBuilder();
        String m = args[0];
        switch (m) {
            case "seen" -> out.append(seen());
            case "heldSeen" -> out.append(heldSeen());
            case "derivedLimit" -> out.append(derivedLimit());
            case "appendThenLogged" -> out.append(appendThenLogged());
            case "appendThenLoggedThroughLambda" -> out.append(appendThenLoggedThroughLambda());
            case "setThenBoxed" -> out.append(setThenBoxed(5));
            case "addThenItems" -> out.append(addThenItems());
            case "setThenReflected" -> out.append(setThenReflected(5));
            case "setThenOwn" -> out.append(setThenOwn(5));
            case "turkishThenLowered" -> out.append(turkishThenLowered());
            case "setThenCopied" -> out.append(setThenCopied(5));
            case "setThenCloned" -> out.append(setThenCloned(5));
            case "setThenCopiedOf" -> out.append(setThenCopiedOf(5));
            case "setThenZeroKey" -> out.append(setThenZeroKey(5));
            case "pinged" -> {
                try {
                    out.append(pinged());
                } catch (StackOverflowError e) {
                    out.append("StackOverflowError");
                }
            }
            case "once" -> {
                try {
                    out.append(Self.once());
                } catch (StackOverflowError e) {
                    out.append("StackOverflowError");
                }
            }
            default -> throw new IllegalArgumentException(m);
        }
        System.out.println(m + "=" + out);
    }
}
