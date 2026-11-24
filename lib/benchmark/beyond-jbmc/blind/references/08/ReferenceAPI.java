import de.intarsys.cwt.font.afm.AFMChar;
public final class ReferenceAPI {
    static AFMChar glyph(int n){return AFMChar.create(((n&1)==0?"C 65":"CH <41>")+" ; WX "+n+" ; N A ;");}
    public static long primary(int n){AFMChar c=glyph(n);return ((long)c.getCode()<<32)|(c.getWidth()&0xffffffffL);}
    public static long control(int n){return "A".equals(glyph(n).getName())?1:0;}
}
