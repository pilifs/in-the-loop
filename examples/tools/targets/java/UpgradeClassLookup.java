import java.net.URL;
import java.security.CodeSource;
import java.lang.invoke.MethodHandles;
import java.lang.invoke.MethodType;

/** Check which original JAR supplies a reported missing type, without initializing it. */
public final class UpgradeClassLookup {
    public static void main(String[] args) throws Exception {
        if (args.length == 1 && args[0].equals("--entries")) {
            java.io.BufferedReader requests = new java.io.BufferedReader(new java.io.InputStreamReader(System.in, "UTF-8"));
            for (String line; (line = requests.readLine()) != null;) {
                String[] fields = line.split("\\t", -1);
                if (fields.length != 3) throw new IllegalArgumentException("expected owner, name and descriptor");
                observeEntry(fields);
            }
            return;
        }
        if (args.length == 1 && args[0].equals("--jdbc-driver")) {
            String url = new java.io.BufferedReader(new java.io.InputStreamReader(System.in, "UTF-8")).readLine();
            try {
                Class<?> type = java.sql.DriverManager.getDriver(url).getClass();
                CodeSource source = type.getProtectionDomain().getCodeSource();
                String origin = source == null ? "runtime" : source.getLocation().toURI().toASCIIString();
                System.out.println("UPGRADE-DRIVER selected " + type.getName() + " " + origin);
            } catch (java.sql.SQLException e) {
                System.out.println("UPGRADE-DRIVER " + ("08001".equals(e.getSQLState()) ? "none " : "unresolved ") + e.getSQLState());
            }
            return;
        }
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

    private static void observeEntry(String[] request) throws Exception {
        String owner = request[0], name = request[1], descriptor = request[2];
        ClassLoader loader = UpgradeClassLookup.class.getClassLoader();
        String source = "-", member = "-", hash = "-", defining = "-", implementation = "-", kind = "-", status = "bound";
        try {
            Class<?> type = Class.forName(owner, false, loader);
            defining = type.getClassLoader() == null ? "bootstrap" : type.getClassLoader().getClass().getName();
            CodeSource origin = type.getProtectionDomain().getCodeSource();
            if (origin == null) throw new IllegalArgumentException("no application code source");
            source = origin.getLocation().toURI().toASCIIString();
            member = owner.replace('.', '/') + ".class";
            URL resource = type.getResource("/" + member);
            java.net.URLConnection connection = resource.openConnection();
            if (connection instanceof java.net.JarURLConnection) {
                java.net.JarURLConnection jar = (java.net.JarURLConnection) connection;
                if (!jar.getJarFileURL().toURI().equals(origin.getLocation().toURI()))
                    throw new IllegalArgumentException("class resource and definition have different origins");
                member = jar.getEntryName();
            }
            java.security.MessageDigest digest = java.security.MessageDigest.getInstance("SHA-256");
            try (java.io.InputStream in = connection.getInputStream()) {
                byte[] buffer = new byte[8192];
                for (int n; (n = in.read(buffer)) != -1;) digest.update(buffer, 0, n);
            }
            StringBuilder hex = new StringBuilder();
            for (byte b : digest.digest()) hex.append(String.format("%02x", b & 255));
            hash = hex.toString();
            if (!name.isEmpty()) {
                MethodType signature = MethodType.fromMethodDescriptorString(descriptor, loader);
                MethodHandles.Lookup lookup = MethodHandles.publicLookup();
                java.lang.invoke.MethodHandle handle;
                if (name.equals("<init>")) {
                    kind = "invokespecial";
                    handle = lookup.findConstructor(type, signature);
                } else {
                    try {
                        kind = type.isInterface() ? "invokeinterface" : "invokevirtual";
                        handle = lookup.findVirtual(type, name, signature);
                    } catch (IllegalAccessException wrongKind) {
                        kind = "invokestatic";
                        handle = lookup.findStatic(type, name, signature);
                    }
                }
                implementation = lookup.revealDirect(handle).getDeclaringClass().getName();
            }
        } catch (Exception | LinkageError e) {
            status = e.getClass().getName();
        }
        System.out.println(String.join("\t", "ENTRY", owner, name, descriptor, status, source, member, hash,
                                       defining, implementation, kind, loader.getClass().getName()));
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
