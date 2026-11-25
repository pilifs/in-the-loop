import java.util.Arrays;
import java.util.Random;
import org.apache.commons.rng.RandomProviderState;
import org.apache.commons.rng.core.source32.JDKRandom;

public class PublicCaller {
    static final long SEED = 8796746234L;

    static int[] draws(JDKRandom source) {
        int[] values = new int[10];
        for (int i = 0; i < values.length; i++) values[i] = source.nextInt();
        return values;
    }

    static int[] reference(long seed) {
        Random oracle = new Random(seed);
        for (int i = 0; i < 10; i++) oracle.nextInt();
        int[] values = new int[10];
        for (int i = 0; i < values.length; i++) values[i] = oracle.nextInt();
        return values;
    }

    static String restore(JDKRandom receiver, RandomProviderState state) {
        try {
            receiver.restoreState(state);
            return "ok";
        } catch (IllegalStateException e) {
            return e.getClass().getSimpleName();
        }
    }

    static String continuation(JDKRandom source) {
        StringBuilder bits = new StringBuilder();
        for (int i = 0; i < 35; i++) bits.append(source.nextBoolean() ? '1' : '0');
        return bits + "/" + source.nextInt();
    }

    static String bitOracle() {
        Random jdk = new Random(SEED);
        int first = jdk.nextInt(), second = jdk.nextInt();
        StringBuilder bits = new StringBuilder();
        for (int i = 3; i < 38; i++) {
            bits.append(((i < 32 ? first : second) >>> (i % 32)) & 1);
        }
        return bits + "/" + jdk.nextInt();
    }

    public static String observe(String[] args) {
        JDKRandom donor = new JDKRandom(SEED);
        if (args[0].equals("bits")) {
            for (int i = 0; i < 3; i++) donor.nextBoolean();
            RandomProviderState checkpoint = donor.saveState();
            String result = "oracle=" + bitOracle() + " donor=" + continuation(donor);
            for (int resumeAt : new int[]{0, 19}) {
                JDKRandom receiver = new JDKRandom(SEED + resumeAt + 1);
                for (int i = 0; i < resumeAt; i++) receiver.nextBoolean();
                result += " at" + resumeAt + "=" + restore(receiver, checkpoint) + "/" + continuation(receiver);
            }
            return result;
        }
        draws(donor);
        RandomProviderState checkpoint = donor.saveState();
        int[] expected = reference(SEED);
        int[] uninterrupted = draws(donor);
        if (args[0].equals("self")) {
            String status = restore(donor, checkpoint);
            int[] replay = draws(donor);
            return status + " first=" + Arrays.toString(uninterrupted) + " replay=" + Arrays.toString(replay)
                    + " oracle=" + (Arrays.equals(expected, uninterrupted) && Arrays.equals(expected, replay));
        }
        JDKRandom receiver = new JDKRandom(SEED + 1);
        draws(receiver);
        String status = restore(receiver, checkpoint);
        int[] actual = draws(receiver);
        return status + " draws=" + Arrays.toString(actual) + " donorOracle=" + Arrays.equals(expected, uninterrupted)
                + " receiverMatchesDonor=" + Arrays.equals(expected, actual)
                + " receiverMatchesOwn=" + Arrays.equals(reference(SEED + 1), actual);
    }
}
