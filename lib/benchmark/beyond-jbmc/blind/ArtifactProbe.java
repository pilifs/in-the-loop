import java.io.*;
import java.lang.reflect.*;
import java.nio.charset.StandardCharsets;
import java.util.Base64;

/** Invoke only the generated public caller. Encode scalar, String, and primitive-array observations without calling application toString. */
public final class ArtifactProbe {
    static Object seed(Class<?> type, int index) {
        if (type.isArray()) {
            int len = index == 0 ? 0 : index % 4 + 1;
            Object a = Array.newInstance(type.getComponentType(), len);
            for (int i=0; i<len; i++) Array.set(a,i,seed(type.getComponentType(),index+i));
            return a;
        }
        int[] ints = {0,1,-1,2,127,128,255,256,16383,16384,Integer.MIN_VALUE,Integer.MAX_VALUE};
        int n=ints[index%ints.length];
        if (type==boolean.class) return (index&1)!=0;
        if (type==byte.class) return (byte)n;
        if (type==short.class) return (short)n;
        if (type==char.class) return (char)n;
        if (type==int.class) return n;
        if (type==long.class) return index==10 ? Long.MIN_VALUE : index==11 ? Long.MAX_VALUE : (long)n;
        if (type==float.class) return index==7 ? -0.0f : (float)n;
        if (type==double.class) return index==7 ? -0.0d : (double)n;
        if (type==String.class) return new String[]{"","0","1","-1","a","A"," ","0.","1.0","x.y","\u212a","\u0661"}[index%12];
        throw new IllegalArgumentException("unsupported generated parameter");
    }

    static Object literal(DataInputStream in, Class<?> t) throws IOException {
        if (!t.isPrimitive() && !in.readBoolean()) return null;
        if (t.isArray()) {
            int length=in.readUnsignedShort();
            Object a=Array.newInstance(t.getComponentType(),length);
            for(int i=0;i<length;++i) Array.set(a,i,literal(in,t.getComponentType()));
            return a;
        }
        if (t==String.class) {
            char[] units=new char[in.readUnsignedShort()];
            for(int i=0;i<units.length;++i) units[i]=in.readChar();
            return new String(units);
        }
        if(t==boolean.class) return in.readBoolean();
        if(t==byte.class) return in.readByte();
        if(t==short.class) return in.readShort();
        if(t==char.class) return in.readChar();
        if(t==int.class) return in.readInt();
        if(t==long.class) return in.readLong();
        if(t==float.class) return Float.intBitsToFloat(in.readInt());
        if(t==double.class) return Double.longBitsToDouble(in.readLong());
        throw new IllegalArgumentException("unsupported witness parameter");
    }

    static String show(Object value) {
        if (value==null) return "null";
        if (value.getClass().isArray()) {
            StringBuilder b=new StringBuilder("[");
            for (int i=0; i<Array.getLength(value); i++) {
                if (i>0) b.append(',');
                b.append(show(Array.get(value,i)));
            }
            return b.append(']').toString();
        }
        if (value instanceof String s) {
            StringBuilder b=new StringBuilder("u");
            for (int i=0; i<s.length(); i++) b.append(String.format("%04x",(int)s.charAt(i)));
            return b.toString();
        }
        if (value instanceof Float f) return "f"+Integer.toHexString(Float.floatToRawIntBits(f));
        if (value instanceof Double d) return "d"+Long.toHexString(Double.doubleToRawLongBits(d));
        if (value instanceof Character c) return Integer.toString(c);
        if (value instanceof Number || value instanceof Boolean) return value.toString();
        throw new IllegalArgumentException("unsupported observation");
    }

    public static void main(String[] args) throws Exception {
        Class<?> owner=Class.forName("PublicCaller", false, ArtifactProbe.class.getClassLoader());
        Method method=null;
        for (Method m:owner.getDeclaredMethods()) if (m.getName().equals("observe")) method=m;
        int trial=Integer.parseInt(args[0]);
        Object[] inputs=new Object[method.getParameterCount()];
        if (args.length == 5) {
            try (DataInputStream in = new DataInputStream(new FileInputStream(args[4]))) {
                for (int i=0; i<inputs.length; ++i) inputs[i]=literal(in,method.getParameterTypes()[i]);
                if (in.read()!=-1) throw new IOException("trailing witness data");
            }
        } else {
            for (int i=0; i<inputs.length; ++i) inputs[i]=seed(method.getParameterTypes()[i], (trial + i * trial) % 12);
        }
        String before=show(inputs);
        String value;
        boolean returned=false, stackReached=false;
        try {
            value="return " + show(method.invoke(null,inputs));
            returned=true;
        } catch (InvocationTargetException e) {
            Throwable t=e.getCause();
            value="throw " + t.getClass().getName();
            for (StackTraceElement frame:t.getStackTrace())
                if (frame.getClassName().equals(args[1]) && frame.getMethodName().equals(args[2])) stackReached=true;
        }
        // Write to a dedicated FD-backed result file. Application stdout is not part of these fields.
        try (DataOutputStream out = new DataOutputStream(new FileOutputStream(args[3]))) {
            for (String field:new String[]{before,value,show(inputs),Boolean.toString(returned),Boolean.toString(stackReached)})
                out.write((Base64.getEncoder().encodeToString(field.getBytes(StandardCharsets.UTF_8))+"\n").getBytes(StandardCharsets.US_ASCII));
        }
    }
}
