import java.io.InputStream;
import java.lang.reflect.Method;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.HexFormat;

public final class Observe {
    public static void main(String[] args) throws Exception {
        boolean wide = args[0].equals("Longs");
        Class<?> owner = Class.forName("com.google.common.primitives." + args[0]);
        long[] numbers = args[2].equals("-") ? new long[0] :
            Arrays.stream(args[2].split(",")).mapToLong(Long::parseLong).toArray();
        Object array;
        Object target;
        if (wide) {
            array = numbers;
            target = Long.valueOf(args[1]);
        } else {
            array = Arrays.stream(numbers).mapToInt(Math::toIntExact).toArray();
            target = Integer.valueOf(args[1]);
        }
        Method method = owner.getMethod("indexOf", array.getClass(), wide ? long.class : int.class);
        try (InputStream in = owner.getResourceAsStream(owner.getSimpleName() + ".class")) {
            System.out.println("entered " + HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(in.readAllBytes())));
        }
        System.out.flush();
        Object result = method.invoke(null, array, target);
        System.out.println("return " + result);
        System.out.println("heap " + (wide ? Arrays.toString((long[])array) : Arrays.toString((int[])array)));
    }
}
