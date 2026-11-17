package app;

import java.util.function.IntUnaryOperator;

/**
 * The same in both versions. Each method calls an application class through a JDK interface, and the class's own code
 * or the static it reads is what the versions change (Step, Config).
 */
public class Entry {
    /** One call: the code reached is Step's, through IntUnaryOperator. */
    public static int supplied(int k) {
        IntUnaryOperator s = new Step();
        return s.applyAsInt(k);
    }

    /** The same call in a loop past the bound: Step's private helper is what the versions change. */
    public static int summed(int k) {
        IntUnaryOperator s = new Step();
        int acc = 0;
        for (int i = 0; i < k; i++) {
            acc += s.applyAsInt(i);
        }
        return acc;
    }

    /** A loop past the bound through an operator that reads Config's static, which its initializer sets. */
    public static int configured(int k) {
        IntUnaryOperator s = new Setting();
        int acc = s.applyAsInt(0);
        for (int i = 0; i < k; i++) {
            acc += s.applyAsInt(i);
        }
        return acc;
    }

    public static void main(String[] args) {
        System.out.println("supplied=" + supplied(1001) + " summed=" + summed(1002) + " configured=" + configured(1002));
    }
}
