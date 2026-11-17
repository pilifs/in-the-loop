package bc;

/** An initializer that writes into an object another class's static holds, then sets its own. */
public class Boxed {
    public static int k;

    static {
        Boxes.BOX.value = 5;
        k = 7;
    }
}
