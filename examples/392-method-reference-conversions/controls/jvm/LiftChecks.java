public class LiftChecks {
 public static void correct(int x,int y) { assert Lift.primitiveGood(x,y); }
 public static void wrong(int x,int y) { assert Lift.primitiveWrong(x,y); }
 public static void reach() {Lift.lift().cmp(2,3);assert false;}
 public static void transfer(short x, short y) {assert Lift.returnGood(x,y);}
 public static void transferWrong(short x,short y) {assert Lift.returnWrong(x,y);}
 public static void boxed(int x,int y) {assert Lift.boxedGood(x,y);}
 public static void badBox(int x,int y) {assert Lift.boxedWrong(x,y);}
 public static void boxNull() {assert Lift.boxedNull();}
 public static void boxNullWrong() {assert !Lift.boxedNull();}
 public static void staticOK(int x,int y) {assert Lift.staticGood(x,y);}
 public static void staticBad(int x,int y) {assert Lift.staticWrong(x,y);}
 public static void main(String[] a) {for(int x: new int[]{Integer.MIN_VALUE,-1,0,1,Integer.MAX_VALUE})for(int y: new int[]{Integer.MIN_VALUE,-1,0,1,Integer.MAX_VALUE}){correct(x,y);boxed(x,y);transfer((short)x,(short)y);}boxNull();try{wrong(-1,0);throw new Error();}catch(AssertionError e){}try{transferWrong((short)-1,(short)0);throw new Error();}catch(AssertionError e){}try{boxNullWrong();throw new Error();}catch(AssertionError e){}}
}
