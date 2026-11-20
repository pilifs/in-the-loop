package reservations;

import java.util.Collections;
import java.util.HashMap;
import java.util.Map;

public class Slots {
    final Map<String,String> slots = Collections.synchronizedMap(new HashMap<>());
    public boolean reserve(String key, String owner) {
        synchronized (slots) {
            if (slots.containsKey(key)) return false;
            slots.put(key, owner);
            return true;
        }
    }
    protected void between() {}
}
