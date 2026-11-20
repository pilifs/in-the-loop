package cubegrid;

import org.intheloop.controls.Grid;
import static org.intheloop.controls.Grid.fields;
import org.apache.commons.geometry.euclidean.threed.*;

public final class Cases {
    private static final double T=1e-10;
    public static void main(String[] args) {
        int[][] starts={{-2,-2,-2},{1,1,1},{4,4,4},{1,1,1},{-2,1,1},{1,4,1}};
        int[][] dirs={{1,1,1},{1,1,1},{-1,-1,-1},{-1,-1,-1},{1,0,0},{0,-1,0}};
        for(int code=0;code<starts.length;code++) {
            int[] s=starts[code],v=dirs[code];
            Vector3D start=Vector3D.of(s[0]/2.0,s[1]/2.0,s[2]/2.0);
            Line diagonal=new Line(Vector3D.ZERO,Vector3D.of(1,1,1),T);
            Line line=code<2?diagonal:code<4?diagonal.revert():new Line(start,start.add(Vector3D.of(v[0],v[1],v[2])),T);
            PolyhedronsSet cube=new PolyhedronsSet(0,1,0,1,0,1,T);
            SubPlane hit=(SubPlane)cube.firstIntersection(start,line);
            Vector3D point=hit==null?null:((Plane)hit.getHyperplane()).intersection(line);
            Grid.row(code,fields("startTimesTwo",s,"direction",v,"tolerance","1e-10"),
                    fields("hit",hit!=null,"point",point==null?null:new String[]{Double.toString(point.getX()),Double.toString(point.getY()),Double.toString(point.getZ())}),
                    fields("hit",Projection.hit(code),"point",Projection.point(code)));
        }
    }
}
