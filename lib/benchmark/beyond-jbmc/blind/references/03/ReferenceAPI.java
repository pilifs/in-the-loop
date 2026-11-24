import org.codehaus.plexus.component.annotations.Component;
import org.eclipse.sisu.plexus.ComponentImpl;
public final class ReferenceAPI {
    @Component(role=Runnable.class) public static class Default {}
    @Component(role=Runnable.class,hint="Named") public static class Named {}
    static Component read(int n) {return (n==0?Default.class:Named.class).getAnnotation(Component.class);}
    static Component copy(Component a){return new ComponentImpl(a.role(),a.hint(),a.instantiationStrategy(),a.description());}
    public static long primary(int n) {
        Component a=read(n), b=copy(a);
        return a.equals(b) && b.equals(a) && a.hashCode()==b.hashCode() && !b.equals(read(1-n)) ? 1:0;
    }
    public static long control(int n) {Component a=copy(read(n));return a.annotationType()==Component.class && a.role()==Runnable.class?1:0;}
}
