public class MadeRows {
  static int[][] make(int x,int y,boolean tied) {int[] u={x};return new int[][]{u,tied?u:new int[]{y}};}
  public static boolean reverse(int x,int y,boolean tied) {return RaggedProof.reversed(make(x,y,tied));}
  public static boolean iterator(int x,int y,boolean tied) {return RaggedProof.iter(make(x,y,tied));}
  public static boolean alwaysDistinct(int x,int y,boolean tied){return RaggedProof.distinct(make(x,y,tied));}
}
