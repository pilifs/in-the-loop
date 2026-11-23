import java.io.IOException;
import org.apache.commons.text.translate.UnicodeUnpairedSurrogateRemover;

public final class SurrogateOracle {
    static final UnicodeUnpairedSurrogateRemover REMOVER = new UnicodeUnpairedSurrogateRemover();
    static void check(int a, int b, SurrogateUnits.Recording writer) throws IOException {
        SurrogateUnits.Two sequence = new SurrogateUnits.Two((char)a, (char)b);
        boolean pair = a >= 0xd800 && a < 0xdc00 && b >= 0xdc00 && b < 0xe000;
        int first = a >= 0xd800 && a < 0xe000 && !pair ? 1 : 0;
        int second = b >= 0xd800 && b < 0xe000 ? 1 : 0;
        if (REMOVER.translate(sequence,0,writer) != first || REMOVER.translate(sequence,1,writer) != second
                || writer.units != 0) throw new AssertionError();
        if (pair) {
            int codePoint = 0x10000 + ((a - 0xd800) << 10) + b - 0xdc00;
            if (Character.codePointAt(sequence,0) != codePoint || Character.codePointBefore(sequence,2) != codePoint)
                throw new AssertionError();
        }
    }
    public static void main(String[] args) throws IOException {
        SurrogateUnits.Recording writer = new SurrogateUnits.Recording();
        for (int a=0xd800; a<0xdc00; a++) for (int b=0xdc00; b<0xe000; b++) check(a,b,writer);
        int[] starts = {0,0x07c0,0x7fc0,0xbfc0,0xd7c0,0xd800,0xdbc0,0xdc00,0xdfc0,0xe000,0xefc0,0xffc0};
        for (int left : starts) for (int right : starts)
            for (int i=0; i<64; i++) for (int j=0; j<64; j++) check(left+i,right+j,writer);
        System.out.println("1048576 valid pairs and 589824 boundary pairs at both offsets; zero writer units");
    }
}
