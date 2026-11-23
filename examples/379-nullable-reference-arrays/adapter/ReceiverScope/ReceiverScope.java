public final class ReceiverScope {
    static class Parent { int value() { return 1; } }
    static class Child extends Parent { @Override int value() { return 2; } }
    static boolean parentAnswer(Parent p) { return p == null || p.value() == 1; }
    public static boolean exact(boolean absent) { return parentAnswer(absent ? null : new Parent()); }
    public static boolean parentOrChild(int choice) { return parentAnswer(choice == 0 ? null : choice == 1 ? new Parent() : new Child()); }
}
