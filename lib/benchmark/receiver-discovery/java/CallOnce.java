package org.intheloop.observation;
import java.lang.invoke.MethodType;
import java.lang.reflect.InvocationTargetException;
import java.security.MessageDigest;
import java.util.HexFormat;

public final class CallOnce {
    public static void main(String[] args) throws Exception {
        var loader = CallOnce.class.getClassLoader();
        var subject = Class.forName(args[0], false, loader);
        try (var stream = subject.getResourceAsStream("/" + args[0].replace('.', '/') + ".class")) {
            System.out.println("class " + HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(stream.readAllBytes())));
        }
        var entry = Class.forName(args[1], false, loader);
        var type = MethodType.fromMethodDescriptorString(args[3], loader);
        var method = entry.getDeclaredMethod(args[2], type.parameterArray());
        if (!method.trySetAccessible()) throw new IllegalAccessException(method.toString());
        Object[] values = new Object[type.parameterCount()];
        if (args.length != values.length + 4) throw new IllegalArgumentException("entry arguments");
        for (int i=0; i<values.length; i++) {
            String a = args[i+4];
            values[i] = switch (type.parameterType(i).getName()) {
                case "int" -> Integer.valueOf(a); case "long" -> Long.valueOf(a);
                case "byte" -> Byte.valueOf(a); case "short" -> Short.valueOf(a);
                case "char" -> Character.valueOf((char)Integer.parseInt(a));
                case "boolean" -> switch(a) {case "true", "1" -> true; case "false", "0" -> false; default -> throw new IllegalArgumentException(a);};
                case "float" -> Float.intBitsToFloat(Integer.parseUnsignedInt(a,16));
                case "double" -> Double.longBitsToDouble(Long.parseUnsignedLong(a,16));
                default -> throw new IllegalArgumentException("unsupported replay argument " + type.parameterType(i));
            };
        }
        try { System.out.println("returned " + method.invoke(null,values)); }
        catch (InvocationTargetException e) { System.out.println("escaped " + e.getCause().getClass().getName()); }
    }
}
