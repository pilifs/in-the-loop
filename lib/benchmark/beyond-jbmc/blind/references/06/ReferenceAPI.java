import org.parboiled.buffers.DefaultInputBuffer;
import org.parboiled.support.Position;
public final class ReferenceAPI {
    static DefaultInputBuffer buf(){return new DefaultInputBuffer("abcd\nef\r\n\ngh\n\n".toCharArray());}
    public static long primary(int n){Position p=buf().getPosition(n);return 100L*p.line+p.column;}
    public static long control(int n){DefaultInputBuffer b=buf();return b.extractLine(2).equals("ef") && b.extractLine(3).isEmpty()?1:0;}
}
