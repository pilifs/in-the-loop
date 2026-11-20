import java.util.HashMap;

/** Exhaust the actual delegate methods on every write history reachable with two reservations. */
class MapTransitions {
    static final String[] KEYS = {"first", "second"};
    static final String[] OWNERS = {null, "A", "B"};

    static int owner(String value) {
        return value == null ? 0 : value.equals("A") ? 1 : value.equals("B") ? 2 : -1;
    }

    public static void main(String[] args) {
        for (int length = 0, words = 1; length <= 2; length++, words *= 4) {
            for (int word = 0; word < words; word++) {
                for (int key = 0; key < 2; key++) {
                    for (int action = 0; action <= (length == 2 ? 0 : 2); action++) {
                        HashMap<String,String> map = new HashMap<>();
                        int history = word;
                        for (int step = 0; step < length; step++, history /= 4) {
                            map.put(KEYS[(history % 4) / 2], OWNERS[1 + history % 2]);
                        }
                        int a = owner(map.get(KEYS[0])), b = owner(map.get(KEYS[1]));
                        int value = action == 0 ? (map.containsKey(KEYS[key]) ? 1 : 0)
                                                : owner(map.put(KEYS[key], OWNERS[action]));
                        System.out.printf("%d %d %d %d %d %d %d %d %d %d%n", length, word, a, b, key, action,
                                value, owner(map.get(KEYS[0])), owner(map.get(KEYS[1])), map.size());
                    }
                }
            }
        }
    }
}
