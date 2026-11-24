import java.io.IOException;
public final class PayloadFirstClaims {
    static boolean check(int h,int v,boolean old)throws IOException {
        int length=1,remaining=v;
        while((remaining & ~127)!=0){remaining>>>=7;++length;}
        int end=5+length;
        byte[] frame=new byte[11];frame[0]=0x33;frame[end]=0x55;
        int written=old?before.PayloadFirst.write(frame,h,v):PayloadFirst.write(frame,h,v);
        int[] r=old?PayloadFirst.read(frame):before.PayloadFirst.read(frame);
        return written==end && r[2]==end && r[0]==v && r[1]==Integer.reverseBytes(h) && frame[0]==0x33 && frame[end]==0x55;
    }
    public static boolean oldNew(int header,int payload)throws IOException{return check(header,payload,true);}
    public static boolean newOld(int header,int payload)throws IOException{return check(header,payload,false);}
}
