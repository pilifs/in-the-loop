import java.util.Comparator;
import com.google.common.collect.ComparisonChain;
import com.google.common.primitives.Longs;
public class Chain {
 public static int guarded(boolean active,Integer x,Integer y) {
  Comparator<Integer> cmp=Longs::compare;
  return ComparisonChain.start().compare(active?0:1,0).compare(x,y,cmp).result();
 }
 public static boolean good(int x,int y){return guarded(true,x,y)==(x>y?1:x<y?-1:0);}
 public static boolean wrong(int x,int y){return guarded(true,x,y)>=0;}
 public static boolean skipsNull(){return guarded(false,null,null)==1;}
 public static boolean rejectsNull(){try{guarded(true,null,0);return false;}catch(NullPointerException e){return true;}}
}
