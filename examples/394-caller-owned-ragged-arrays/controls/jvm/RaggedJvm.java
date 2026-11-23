public class RaggedJvm {
 interface Op { void run(int[][] a); }
 static int tests, w1, w2, shared, reached;
 static final int[][] rows=new int[14][];
 static {int k=1; rows[k++]=new int[0]; for(int a=-1;a<=1;a++)rows[k++]=new int[]{a}; for(int a=-1;a<=1;a++)for(int b=-1;b<=1;b++)rows[k++]=new int[]{a,b};}
 static int[][] graph(int a,int b,boolean tie) {
  int[] left=rows[a]==null?null:rows[a].clone(),right=tie?left:(rows[b]==null?null:rows[b].clone());
  return new int[][]{left,right};
 }
 static int fails(Op op,int[][] a) {try{op.run(a);return 0;}catch(AssertionError e){return 1;}}
 static void check(int a,int b,boolean tie) {
   tests++; if(fails(Ragged::reversed,graph(a,b,tie))!=0 || fails(Ragged::iter,graph(a,b,tie))!=0)throw new AssertionError();
   w1+=fails(Ragged::wrong,graph(a,b,tie));w2+=fails(Ragged::snapshot,graph(a,b,tie));shared+=fails(Ragged::cross,graph(a,b,tie));reached+=fails(Ragged::reach,graph(a,b,tie));
 }
 public static void main(String[] args){
  for(int a=0;a<14;a++)for(int b=0;b<14;b++)check(a,b,false);
  for(int a=1;a<14;a++)check(a,a,true);
  if(fails(Ragged::wrong,new int[][]{new int[0],null})!=1 || fails(Ragged::snapshot,new int[][]{new int[0],null})!=1)throw new AssertionError();
  System.out.println("total="+tests+" bad inversion="+w1+" bad snapshot="+w2+" shared nonempty="+shared+" both nonempty="+reached);
 }
}
