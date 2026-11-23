import org.apache.commons.math3.util.MathArrays;
import org.apache.commons.math3.exception.DimensionMismatchException;
public class MatrixJvm {
  static long[] row(int n){return n<0?null:new long[n];}
  public static void main(String[] args) {
    int checks=0, normal=0, nulls=0, mismatch=0;
    for(int n=-1;n<=2;n++)for(int x=-1;x<=2;x++)for(int y=-1;y<=2;y++){
      if(n<1 && (x!=-1 || y!=-1))continue;
      if(n<2 && y!=-1)continue;
      long[][] m=n<0?null:n==0?new long[0][]:n==1?new long[][]{row(x)}:new long[][]{row(x),row(y)};
      if(n<0)continue;
      if(!MatrixRows.shape(m))throw new AssertionError();
      try{MathArrays.checkRectangular(m);normal++;
         if(n==2 && (x<0 || y<0 || x!=y))throw new AssertionError();}
      catch(NullPointerException e){nulls++;if(n!=2 || (x>=0 && y>=0))throw new AssertionError();}
      catch(DimensionMismatchException e){mismatch++;if(n!=2 || x<0 || y<0 || x==y || e.getDimension()!=x || e.getArgument().intValue()!=y)throw new AssertionError();}
      checks++;
    }
    if(MatrixRows.noNull(new long[][]{null}))throw new AssertionError();
    System.out.println("nonnull outer shape census="+checks+" normal="+normal+" NPE="+nulls+" dimensions="+mismatch);
  }
}
