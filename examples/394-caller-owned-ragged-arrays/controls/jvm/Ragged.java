import org.apache.commons.lang3.ArrayUtils;
import org.apache.commons.collections4.iterators.ObjectArrayIterator;
public class Ragged {
 public static void reversed(int[][] a) {
   if(a==null || a.length!=2) return;
   int[] left=a[0], right=a[1];
   ArrayUtils.reverse(a);
   assert a[0]==right && a[1]==left;
   if(left==null || right==null || left.length==0 || right.length==0) return;
   int r=right[0];
   left[0]=~left[0];
   assert (right[0]!=r)==(left==right);
 }
 public static void wrong(int[][] a) {
   if(a==null || a.length!=2) return;
   int[] left=a[0];
   ArrayUtils.reverse(a);
   assert a[0]==left;
 }
 public static void iter(int[][] a) {
   if(a==null || a.length!=2) return;
   int[] first=a[0]; ObjectArrayIterator<int[]> it=new ObjectArrayIterator<>(a);
   assert it.next()==first;
   a[1]=first;
   assert it.next()==first && !it.hasNext();
   it.reset(); assert it.next()==first;
 }
 public static void snapshot(int[][] a) {
   if(a==null || a.length!=2) return;
   int[] a1=a[1]; ObjectArrayIterator<int[]> it=new ObjectArrayIterator<>(a);
   it.next(); a[1]=a[0]; assert it.next()==a1;
 }
 public static void reach(int[][] a) {
   if(a==null || a.length!=2 || a[0]==null || a[1]==null || a[0].length==0 || a[1].length==0) return;
   assert false;
 }
 public static void cross(int[][] a) {
   if(a!=null && a.length==2 && a[0]!=null && a[0].length>0 && a[1]==a[0]) assert false;
 }
}
