public class NestedApp {
    public static void main(String[] args) throws Exception {
        BootArchive.childBinding();
        var loader = Thread.currentThread().getContextClassLoader();
        if (args[0].equals("miss")) {
            try { loader.loadClass("demo.DoesNotExist"); throw new AssertionError("unexpected class"); }
            catch (ClassNotFoundException expected) { }
        }
        var type = loader.loadClass("demo.Application");
        if (type.getClassLoader() != loader) throw new AssertionError("class is outside nested library");
        System.out.println("OBS " + type.getPackage().getImplementationVersion());
    }
}
