package app;

/** What `Seeded`'s initializer takes its table from: the only class of the `seeded` pair that differs. */
final class Seed {
    private Seed() {}

    static int[] table() {
        return new int[] {3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5, 8, 9, 7, 9, 3};
    }
}
