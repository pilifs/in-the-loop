package fractiongrid;

import org.intheloop.controls.Grid;
import static org.intheloop.controls.Grid.fields;
import java.util.HexFormat;
import org.apache.commons.math3.fraction.Fraction;

public final class Cases {
    public static void main(String[] args) {
        int code=0;
        for(int n:new int[]{21474834, 21474835, 21474836, 21474837, 21474838, -21474834, -21474835, -21474836, -21474837, -21474838, -1, 0, 1}) {
            String bits=null,failure=null;
            try { bits=HexFormat.of().toHexDigits(Double.doubleToRawLongBits(new Fraction(n,1).percentageValue())); }
            catch(ArithmeticException ex) { failure=ex.getClass().getName(); }
            Grid.row(code,fields("n",n,"denominator",1),fields("bits",bits,"normal",failure),
                fields("bits",Projection.bits(code),"normal",Projection.normal(code)));
            code++;
        }
    }
}
