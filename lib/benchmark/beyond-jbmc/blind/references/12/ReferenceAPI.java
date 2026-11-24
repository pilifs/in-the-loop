import com.fasterxml.jackson.jr.ob.JSON;
import com.fasterxml.jackson.jr.ob.JSONObjectException;
import java.io.IOException;
public final class ReferenceAPI {
    public enum Item { PLAIN, SPECIAL { public int marker(){return 2;} }; public int marker(){return 1;} }
    static long spelling(Item v) {
        try {String text=JSON.std.asString(v);return text.equals("\""+v.name()+"\"")?1:text.equals("{\"declaringClass\":\"" + Item.class.getName() + "\"}")?2:3;}
        catch(JSONObjectException e){return 4;} catch(IOException e){throw new IllegalStateException(e);}
    }
    public static long primary(int n){return spelling(n==0?Item.PLAIN:Item.SPECIAL);}
    public static long control(int n){return spelling(Item.PLAIN);}
}
