import org.intheloop.observation.CallOnce;
import java.util.Arrays;

/** Set one ordinary process prestate, then invoke the unmodified entry by its JVM descriptor. */
public final class InitialProperty {
    public static void main(String[] args) throws Exception {
        if (args[0].equals("absent")) System.clearProperty(args[1]);
        else if (args[0].equals("value")) System.setProperty(args[1], args[2]);
        else throw new IllegalArgumentException("prestate");
        CallOnce.main(Arrays.copyOfRange(args, 3, args.length));
    }
}
