package fixtures;

public final class RangeLoops {
    static void rangeCheck(int length, int from, int to) {
        if (from > to) throw new IllegalArgumentException();
        if (from < 0) throw new IndexOutOfBoundsException();
        if (to > length) throw new IndexOutOfBoundsException();
    }

    public static void savedValue(int[] a, int from, int to, int value) {
        rangeCheck(a.length, from, to);
        int saved = value;
        for (int i = from; i < to; ++i) a[i] = saved;
    }

    public static void missingStore(int[] a, int from, int to, int value) {
        rangeCheck(a.length, from, to);
        for (int i = from; i < to; ++i) { }
    }

    public static void wrongValue(int[] a, int from, int to, int value) {
        rangeCheck(a.length, from, to);
        for (int i = from; i < to; ++i) a[i] = from;
    }

    static void strictRangeCheck(int length, int from, int to) {
        if (from >= to) throw new IllegalArgumentException();
        if (from < 0) throw new IndexOutOfBoundsException();
        if (to > length) throw new IndexOutOfBoundsException();
    }

    public static void rejectsEmpty(int[] a, int from, int to, int value) {
        strictRangeCheck(a.length, from, to);
        for (int i = from; i < to; ++i) a[i] = value;
    }

    public static int readsFilledRoot(int[] a, int[] other, int from, int to, int value, int k) {
        java.util.Arrays.fill(a, from, to, value);
        return a[k];
    }

    public static void main(String[] args) {
        int[] a = {11, 19};
        savedValue(a, 0, 1, 7);
        System.out.println("savedValue " + java.util.Arrays.toString(a));
        a[0] = 11;
        missingStore(a, 0, 1, 7);
        System.out.println("missingStore " + java.util.Arrays.toString(a));
        wrongValue(a, 0, 1, 7);
        System.out.println("wrongValue " + java.util.Arrays.toString(a));
        try {
            rejectsEmpty(new int[0], 0, 0, 7);
        } catch (IllegalArgumentException e) {
            System.out.println("rejectsEmpty " + e.getClass().getSimpleName());
        }
        try {
            readsFilledRoot(new int[0], new int[]{31}, 0, 0, 7, 0);
        } catch (ArrayIndexOutOfBoundsException e) {
            System.out.println("readsFilledRoot " + e.getClass().getSimpleName());
        }
    }
}
