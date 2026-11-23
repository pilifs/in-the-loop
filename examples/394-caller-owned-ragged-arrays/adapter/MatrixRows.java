import org.apache.commons.math3.util.MathArrays;
import org.apache.commons.math3.exception.DimensionMismatchException;
public class MatrixRows {
  public static boolean shape(long[][] a){
    if(a==null || a.length!=2 || a[0]==null || a[1]==null)return true;
    try{MathArrays.checkRectangular(a);return a[0].length==a[1].length;}
    catch(DimensionMismatchException e){return a[0].length!=a[1].length && e.getDimension()==a[0].length;}
  }
  public static boolean same(long[][] a){
    if(a==null || a.length!=2 || a[0]==null || a[1]==null)return true;
    try{MathArrays.checkRectangular(a);return true;}
    catch(DimensionMismatchException e){return false;}
  }
  public static boolean noNull(long[][] a){
    if(a==null || a.length!=1 || a[0]!=null)return true;
    try{MathArrays.checkRectangular(a);return false;}catch(NullPointerException e){return true;}
  }
  public static boolean rectangular(long[][] a) {
    if(a==null || a.length!=2 || a[0]==null || a[1]==null || a[0].length!=a[1].length)return true;
    MathArrays.checkRectangular(a);return true;
  }
  public static boolean singleShape(long[][] a) {
    if(a==null || a.length!=1 || a[0]!=null)return true;
    MathArrays.checkRectangular(a);return true;
  }
  public static void good(long[][] a){assert rectangular(a);}
  public static void singleGood(long[][] a){assert singleShape(a);}
  public static void correct(long[][] a){assert shape(a);}
  public static void wrong(long[][] a){assert same(a);}
  public static void singleton(long[][] a){assert noNull(a);}
  public static void reach(long[][] a){if(a!=null && a.length==2 && a[0]!=null && a[1]!=null && a[0].length==1 && a[1].length==1){MathArrays.checkRectangular(a);assert false;}}
}
