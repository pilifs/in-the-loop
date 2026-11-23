final class Replay {
 public static void main(String[] args) {
  if (Lift.primitiveWrong(0,1) || Lift.boxedWrong(0,1) || Lift.returnWrong((short)0,(short)1)
   || Lift.staticWrong(0,1073741824) || Lift.staticWrong(-1,0) || !Lift.boxedNull()) throw new AssertionError();
  System.out.println("All exact control inputs replayed.");
 }
}
