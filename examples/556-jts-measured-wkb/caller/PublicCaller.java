import org.locationtech.jts.geom.*;
import org.locationtech.jts.io.*;

import java.nio.*;
import java.util.*;

public class PublicCaller {
    static String write(boolean zm, int order, boolean marker) throws Exception {
        String wkt = zm ? "LINESTRING ZM(1 2 3 4, 5 6 7 8)" : "LINESTRING M(1 2 3, 5 6 7)";
        var line = new WKTReader().read(wkt);
        byte[] bytes = new WKBWriter(4, order, false).write(line);
        int flags =
                ByteBuffer.wrap(bytes, 1, 4)
                        .order(bytes[0] == 1 ? ByteOrder.LITTLE_ENDIAN : ByteOrder.BIG_ENDIAN)
                        .getInt();
        var s = ((LineString) new WKBReader().read(bytes)).getCoordinateSequence();
        List<String> values = new ArrayList<>();
        for (int i = 0; i < s.size(); i++)
            values.add(s.getX(i) + ":" + s.getY(i) + ":" + s.getZ(i) + ":" + s.getM(i));
        return (marker ? bytes[0] + ":" : "")
                + bytes.length
                + "/"
                + ((flags & 0x80000000) != 0 ? "Z" : "")
                + ((flags & 0x40000000) != 0 ? "M" : "")
                + "/"
                + values
                + "/"
                + s.getMeasures();
    }

    public static String observe(String[] a) throws Exception {
        boolean both = a[0].equals("challenge");
        return write(a[0].equals("control"), ByteOrderValues.LITTLE_ENDIAN, both)
                + (both ? " / " + write(false, ByteOrderValues.BIG_ENDIAN, true) : "");
    }
}
