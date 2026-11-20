package reservations;

import java.util.Collections;
import java.util.HashMap;
import java.util.Map;

public class Slots {
    final Map<String,String> slots = Collections.synchronizedMap(new HashMap<>());
    public boolean reserve(String key, String owner) {
        if (slots.containsKey(key)) return false;
        between();
        slots.put(key, owner);
        return true;
    }
    protected void between() {}
}
