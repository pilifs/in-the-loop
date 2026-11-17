package lo;

/**
 * Loops whose later iterations do what the first ones do not, each read after the loop: the challenge stream's
 * attempt to make the loop invariant search (lib/src/bmc/loops.rs) keep something an iteration breaks. Every
 * property the tests state of them is false on a JVM, which main shows.
 */
public final class L {
    private L() {}

    static int count;
    static int hit;

    /** Sets hit on its seventh call: a value a callee writes, and only in a late iteration. */
    static void bump() {
        if (count == 6) {
            hit = 1;
        }
        count++;
    }

    static final class Box {
        int v;
        int w;
    }

    /** The flag is written only once phase reaches 5: n = 6 returns 1. */
    public static int late(int n) {
        int phase = 0;
        int flag = 0;
        for (int i = 0; i < n; i++) {
            if (phase == 5) {
                flag = 1;
            }
            phase++;
        }
        return flag;
    }

    /** The same through a callee and two statics: n = 7 returns 1. */
    public static int callee(int n) {
        for (int i = 0; i < n; i++) {
            bump();
        }
        return hit;
    }

    /** One array under two names, read through one and written through the other: n = 5 returns 9. */
    public static int aliased(int n) {
        int[] a = new int[3];
        int[] b = a;
        for (int i = 0; i < n; i++) {
            if (b[2] == 4) {
                a[0] = 9;
            }
            a[2]++;
        }
        return b[0];
    }

    /** A relation between two cells that only a late iteration meets: n = 4 returns 102. */
    public static int twoCells(int n) {
        int[] c = {0, 0};
        for (int i = 0; i < n; i++) {
            if (c[0] - c[1] == 3) {
                c[0] = 100;
            }
            c[0] += 2;
            c[1] += 1;
        }
        return c[0];
    }

    /** An object reached through a local and through an array's cell: n = 6 returns 7. */
    public static int boxed(int n) {
        Box b = new Box();
        Box[] boxes = {b};
        for (int i = 0; i < n; i++) {
            if (boxes[0].w == 5) {
                b.v = 7;
            }
            b.w++;
        }
        return b.v;
    }

    /** A loop inside a loop, the flag written in the fifth round of both: (5, 5) returns 1. */
    public static int nested(int n, int m) {
        int flag = 0;
        for (int i = 0; i < n; i++) {
            for (int j = 0; j < m; j++) {
                if (i == 4 && j == 4) {
                    flag = 1;
                }
            }
        }
        return flag;
    }

    /** A table of 100 cells written at an index the loop computes: n = 4 returns 4. */
    public static int large(int n) {
        int[] t = new int[100];
        int k = 0;
        for (int i = 0; i < n; i++) {
            t[k] = 1;
            k = (k + 7) % 100;
        }
        return t[0] + t[7] + t[14] + t[21];
    }

    public static void main(String[] args) {
        System.out.println("late=" + late(6) + " callee=" + callee(7) + " aliased=" + aliased(5) + " twoCells=" + twoCells(4) + " boxed=" + boxed(6) + " nested=" + nested(5, 5) + " large=" + large(4));
    }
}
