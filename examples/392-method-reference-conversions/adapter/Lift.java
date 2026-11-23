import com.google.common.primitives.Longs;
import org.apache.commons.lang3.math.NumberUtils;
public class Lift {
 interface Bi { long cmp(int x, int y); }
 interface Box { long cmp(Integer x, Integer y); }
 interface Twice { long cmp(short x, short y); }
 static final Bi lift() { return Longs::compare; }
 static final Box box() { return Longs::compare; }
 static final Twice again() {return NumberUtils::compare;}
 static long oracle(int x,int y) {return (x>y?1:x<y?-1:0);}
 public static boolean primitiveGood(int x,int y) { return lift().cmp(x,y)==oracle(x,y); }
 public static boolean primitiveWrong(int x,int y) {return lift().cmp(x,y)>=0;}
 public static boolean returnGood(short x,short y) {return again().cmp(x,y)==oracle(x,y);}
 public static boolean returnWrong(short x,short y) {return again().cmp(x,y)>=0;}
 public static boolean boxedGood(int x,int y) {return box().cmp(x,y)==oracle(x,y);}
 public static boolean boxedWrong(int x,int y) {return box().cmp(x,y)>=0;}
 public static boolean boxedNull() {try{box().cmp(null,1);return false;}catch(NullPointerException ok){return true;}}
 public static boolean staticGood(int x,int y) {return (long)Longs.compare((long)x,(long)y)==oracle(x,y);}
 public static boolean staticWrong(int x,int y) {return (long)Longs.compare((long)x,(long)y)>=0;}
}
