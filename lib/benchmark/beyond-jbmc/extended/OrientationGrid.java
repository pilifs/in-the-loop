import org.locationtech.jts.algorithm.Orientation;
import org.locationtech.jts.geom.Coordinate;

public final class OrientationGrid {
    static boolean check(int x,int y,int u,int v) {
        long det=(long)x*v-(long)y*u;
        int sign=Long.compare(det,0L);
        Coordinate o=new Coordinate(0,0),p=new Coordinate(x,y),q=new Coordinate(u,v);
        return Orientation.index(o,p,q)==sign && Orientation.index(o,q,p)==-sign;
    }
    public static boolean box(int x,int y,int u,int v) {
        if (x < -8 || x > 8 || y < -8 || y > 8 || u < -8 || u > 8 || v < -8 || v > 8) return true;
        return check(x,y,u,v);
    }
    public static boolean cancellation(int n) {
        if (n<1 || n>1073741822) return true;
        // Two products exceed the binary64 exact-integer range towards the upper end. The determinant is one.
        return check(n,n-1,n+1,n);
    }
}
