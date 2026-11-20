package bridgegrid;

public final class Projection {
    private static Object input(int code) {
        switch(code) { case 0:return null;case 1:return Integer.valueOf(-1);case 2:return Integer.valueOf(0);case 3:return Integer.valueOf(1);default:return "one"; }
    }
    @SuppressWarnings({"rawtypes","unchecked"})
    private static int check(int code,int field) {
        Plus plus=new Plus(); Mapper raw=plus;
        Object value=null; boolean rejected=false;
        try { value=raw.map(input(code)); } catch(ClassCastException e){rejected=true;}
        if(field==1)return rejected==(code==4)?1:0;
        if(field==2)return plus.entries==(code==4?0:1)?1:0;
        if(code==4)return value==null?1:0;
        return value instanceof Integer && ((Integer)value).intValue()==(code==0?99:code-1)?1:0;
    }
    public static int value(int code){return check(code,0);}
    public static int exception(int code){return check(code,1);}
    public static int entries(int code){return check(code,2);}
    @SuppressWarnings({"rawtypes","unchecked"})
    public static int typedAgreement(int code) {
        if(code==4)return -1;
        Integer n=(Integer)input(code);
        Plus typed=new Plus(), erased=new Plus(); Mapper raw=erased;
        return typed.map(n).intValue()==((Integer)raw.map(n)).intValue() && typed.entries==1 && erased.entries==1?1:0;
    }
}
