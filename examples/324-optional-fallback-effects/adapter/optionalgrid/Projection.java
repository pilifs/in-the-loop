package optionalgrid;

import java.util.Optional;

public final class Projection {
    private static int check(int code,boolean trace) {
        Optional<Integer> opt=code==0?Optional.empty():Optional.of(code-1);
        Fallback f=new Fallback();
        int result=Choice.choose(opt,f);
        return trace?(f.calls==(code==0?1:0)?1:0):(result==(code==0?7:code-1)?1:0);
    }
    public static int value(int code){return check(code,false);}
    public static int callbacks(int code){return check(code,true);}
}
