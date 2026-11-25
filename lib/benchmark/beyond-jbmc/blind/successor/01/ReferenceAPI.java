import com.twelvemonkeys.util.TimeoutMap;

public final class ReferenceAPI {
    public static long primary(int n) {
        TimeoutMap<String, Integer> map = new TimeoutMap<>(n == 0 ? -86400000L : 86400000L);
        if (map.size() != 0) throw new AssertionError();
        map.put("key", 7);
        return map.size();
    }
    public static long control(int n) {
        TimeoutMap<String, Integer> map = new TimeoutMap<>(86400000L);
        map.put("unchanged", 7);
        return map.get("unchanged") == 7 ? 1 : 0;
    }
}
