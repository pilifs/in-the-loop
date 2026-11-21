import java.net.URL;
import java.security.CodeSource;
import java.lang.invoke.MethodHandles;
import java.lang.invoke.MethodType;

/** Check which original JAR supplies a reported missing type, without initializing it. */
public final class UpgradeClassLookup {
    public static void main(String[] args) throws Exception {
        if (args.length == 4) {
            lookupMember(args[0], args[1], args[2], args[3]);
            return;
        }
        String name = args[0];
        try {
            Class<?> type = Class.forName(name, false, UpgradeClassLookup.class.getClassLoader());
            CodeSource source = type.getProtectionDomain().getCodeSource();
            URL location = source == null ? null : source.getLocation();
            System.out.println("UPGRADE-LOOKUP found " + (location == null ? "runtime" : location.toURI().toASCIIString()));
        } catch (ClassNotFoundException error) {
            System.out.println("UPGRADE-LOOKUP " + (name.equals(error.getMessage()) ? "missing" : "unresolved"));
        } catch (LinkageError error) {
            System.out.println("UPGRADE-LOOKUP linkage " + error.getClass().getName());
        }
    }

    private static void lookupMember(String owner, String name, String descriptor, String opcode) throws Exception {
        ClassLoader loader = UpgradeClassLookup.class.getClassLoader();
        Class<?> type;
        try {
            type = Class.forName(owner, false, loader);
        } catch (ClassNotFoundException | LinkageError e) {
            System.out.println("UPGRADE-MEMBER unresolved unknown runtime");
            return;
        }
        String status = "found";
        try {
            MethodHandles.Lookup lookup = MethodHandles.publicLookup();
            if (descriptor.startsWith("(")) {
                MethodType signature = MethodType.fromMethodDescriptorString(descriptor, loader);
                if (opcode.equals("invokestatic")) lookup.findStatic(type, name, signature);
                else if (opcode.equals("invokespecial") && name.equals("<init>")) lookup.findConstructor(type, signature);
                else if (opcode.equals("invokevirtual") || opcode.equals("invokeinterface")) lookup.findVirtual(type, name, signature);
                else status = "unresolved";
            } else {
                Class<?> fieldType = MethodType.fromMethodDescriptorString("()" + descriptor, loader).returnType();
                if (opcode.equals("getstatic")) lookup.findStaticGetter(type, name, fieldType);
                else if (opcode.equals("getfield")) lookup.findGetter(type, name, fieldType);
                else if (opcode.equals("putstatic")) lookup.findStaticSetter(type, name, fieldType);
                else if (opcode.equals("putfield")) lookup.findSetter(type, name, fieldType);
                else status = "unresolved";
            }
        } catch (NoSuchFieldException | NoSuchMethodException e) {
            status = "missing";
        } catch (IllegalAccessException | TypeNotPresentException | LinkageError e) {
            status = "unresolved";
        }
        CodeSource source = type.getProtectionDomain().getCodeSource();
        String origin = source == null ? "runtime" : source.getLocation().toURI().toASCIIString();
        System.out.println("UPGRADE-MEMBER " + status + " " + (type.isInterface() ? "interface" : "class") + " " + origin);
    }
}
