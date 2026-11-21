import java.net.URL;
import java.security.CodeSource;

/** Check which original JAR supplies a reported missing type, without initializing it. */
public final class UpgradeClassLookup {
    public static void main(String[] args) throws Exception {
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
}
