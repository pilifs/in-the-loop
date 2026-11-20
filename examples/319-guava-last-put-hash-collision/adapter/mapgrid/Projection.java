package mapgrid;

import com.google.common.collect.ImmutableMap;
import java.util.Map;

public final class Projection {
    private static String key(int digit) { return digit == 0 ? "QED" : digit == 1 ? "R&D" : "X"; }
    public static boolean unique(int code) {
        int mask = 0;
        while (code != 0) {
            code--; int bit = 1 << (code % 3);
            if ((mask & bit) != 0) return false;
            mask |= bit; code /= 3;
        }
        return true;
    }
    private static int check(int code, int field) {
        ImmutableMap.Builder<String,Integer> builder = ImmutableMap.builder();
        int[] last = new int[3];
        int at = 0, count = 0;
        while (code != 0) {
            code--;
            int k = code % 3;
            if (last[k] == 0) count++;
            last[k] = ++at;
            builder.put(key(k),at);
            code /= 3;
        }
        ImmutableMap<String,Integer> map = builder.buildKeepingLast();
        if (field == 0) return map.size() == count ? 1 : 0;
        if (field == 1) {
            for (int k = 0; k < 3; k++) {
                Integer value = map.get(key(k));
                if ((value == null ? 0 : value.intValue()) != last[k]) return 0;
            }
        } else {
            int seen = 0;
            for (Map.Entry<String,Integer> e : map.entrySet()) {
                int k = "QED".equals(e.getKey()) ? 0 : "R&D".equals(e.getKey()) ? 1 : "X".equals(e.getKey()) ? 2 : -1;
                if (k < 0 || (seen & (1 << k)) != 0 || e.getValue().intValue() != last[k]) return 0;
                seen |= 1 << k;
            }
            for (int k = 0; k < 3; k++) if ((last[k] != 0) != ((seen & (1 << k)) != 0)) return 0;
        }
        return 1;
    }
    public static int size(int code) { return check(code,0); }
    public static int lookup(int code) { return check(code,1); }
    public static int entries(int code) { return check(code,2); }
}
