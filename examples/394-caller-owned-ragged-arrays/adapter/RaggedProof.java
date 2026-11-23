import org.apache.commons.lang3.ArrayUtils;
import org.apache.commons.collections4.iterators.ObjectArrayIterator;
public class RaggedProof {
 public static boolean reversed(int[][] a) {
   if(a==null || a.length!=2) return true;
   int[] left=a[0], right=a[1];
   ArrayUtils.reverse(a);
   if(a[0]!=right || a[1]!=left) return false;
   if(left==null || right==null || left.length==0 || right.length==0) return true;
   int r=right[0];left[0]=~left[0];
   return (right[0]!=r)==(left==right);
 }
 public static boolean wrong(int[][] a) {
   if(a==null || a.length!=2) return true;
   int[] left=a[0];ArrayUtils.reverse(a);return a[0]==left;
 }
 public static boolean iter(int[][] a) {
   if(a==null || a.length!=2) return true;
   int[] f=a[0];ObjectArrayIterator<int[]> it=new ObjectArrayIterator<>(a);
   if(it.next()!=f)return false;
   a[1]=f;if(it.next()!=f || it.hasNext())return false;
   it.reset();return it.next()==f;
 }
 public static boolean snapshot(int[][] a) {
   if(a==null || a.length!=2) return true;
   int[] old=a[1];ObjectArrayIterator<int[]> it=new ObjectArrayIterator<>(a);
   it.next();a[1]=a[0];return it.next()==old;
 }
 public static boolean distinct(int[][] a) {
   return a==null || a.length!=2 || a[0]==null || a[0].length==0 || a[1]!=a[0];
 }
 static void choose(int[][] a,boolean tie) {if(tie && a!=null && a.length==2)a[1]=a[0];}
 public static void testReverse(int[][] a){assert reversed(a);}
 public static void testWrong(int[][] a){assert wrong(a);}
 public static void testIter(int[][] a){assert iter(a);}
 public static void testSnapshot(int[][] a){assert snapshot(a);}
 public static void testDistinct(int[][] a){assert distinct(a);}
 public static void testAliasReverse(int[][] a,boolean tie){choose(a,tie);assert reversed(a);}
 public static void testAliasDistinct(int[][] a,boolean tie){choose(a,tie);assert distinct(a);}
}
