package cubegrid;

import org.apache.commons.geometry.euclidean.threed.*;

public final class Projection {
    private static final double T = 1e-10;
    private static int check(int code,boolean coordinates) {
        Vector3D center=Vector3D.of(.5,.5,.5);
        Line line=new Line(Vector3D.ZERO,Vector3D.of(1,1,1),T);
        Vector3D start=code==0?Vector3D.of(-1,-1,-1):code==2?Vector3D.of(2,2,2):center;
        if(code==2||code==3)line=line.revert();
        if(code==4){start=Vector3D.of(-1,.5,.5);line=new Line(start,center,T);}
        if(code==5){start=Vector3D.of(.5,2,.5);line=new Line(start,center,T);}
        PolyhedronsSet cube=new PolyhedronsSet(0,1,0,1,0,1,T);
        SubPlane hit=(SubPlane)cube.firstIntersection(start,line);
        if(hit==null)return 0;
        if(!coordinates)return 1;
        Vector3D v=((Plane)hit.getHyperplane()).intersection(line);
        if(v==null)return 0;
        double[][] expected={{0.0, 0.0, 0.0}, {1.0, 1.0, 1.0}, {1.0, 1.0, 1.0}, {0.0, 0.0, 0.0}, {0.0, 0.5, 0.5}, {0.5, 1.0, 0.5}};
        return Math.abs(v.getX()-expected[code][0])<=T && Math.abs(v.getY()-expected[code][1])<=T
                && Math.abs(v.getZ()-expected[code][2])<=T?1:0;
    }
    public static int hit(int code){return check(code,false);}
    public static int point(int code){return check(code,true);}
}
