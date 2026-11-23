package claims;

public final class MethodReferenceReplay {
    interface Wide { long compare(int first, int second); }
    interface Boxed { long compare(Integer first, Integer second); }
    interface Shorts { long compare(short first, short second); }

    static int compare(long first, long second) {
        return first < second ? -1 : first > second ? 1 : 0;
    }

    static int compareShort(short first, short second) {
        return first - second;
    }

    public static boolean primitive(int x) {
        Wide call = MethodReferenceReplay::compare;
        return call.compare(x, 1) >= 0;
    }

    public static boolean boxed(int x) {
        Boxed call = MethodReferenceReplay::compare;
        return call.compare(x, 1) >= 0;
    }

    public static boolean resultOnly(int x) {
        Shorts call = MethodReferenceReplay::compareShort;
        return call.compare((short)x, (short)1) >= 0;
    }
}
