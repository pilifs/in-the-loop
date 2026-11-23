public class ChainTests {
 public static void good(int x,int y){assert Chain.good(x,y);}
 public static void wrong(int x,int y){assert Chain.wrong(x,y);}
 public static void reach(){Chain.guarded(true,-1,2);assert false;}
 public static void skips(){assert Chain.skipsNull();}
 public static void rejects(){assert Chain.rejectsNull();}
 public static void main(String[] a){good(-1,2);skips();rejects();try{wrong(0,1);throw new Error();}catch(AssertionError e){}}
}
