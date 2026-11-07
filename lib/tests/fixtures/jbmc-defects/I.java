/** The draft report's example for cause 4 in README.md: run on the JVM with `java -ea I`, and with
 * `jbmc I --function I.field` and `jbmc I --function I.iface`. Each assertion holds on the JVM. */
public class I {
    static int log;
    static int mark(int v) { log = log * 10 + v; return v; }
    static class Holder { static int value = 7; }
    static class Sub extends Holder { static { mark(1); } }
    interface Bare { int B = mark(4); }
    interface Greeter { int G = mark(3); default int greet() { return G; } }
    static class Hello implements Bare, Greeter { static int v() { return 0; } }
    public static void field() { int v = Sub.value; assert log == 0 && v == 7; }
    public static void iface() { Hello.v(); assert log == 3; }
    public static void main(String[] args) { field(); iface(); System.out.println("log " + log); }
}
