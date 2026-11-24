import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.Collections;
import java.util.List;
import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

public class UpgradeProbe {
    private static String values(Object array) {
        StringBuilder text = new StringBuilder();
        int length = array instanceof JSONArray ? ((JSONArray)array).length() : ((List<?>)array).size();
        for (int i = 0; i < length; i++) {
            if (i != 0) text.append(',');
            text.append(array instanceof JSONArray ? ((JSONArray)array).get(i) : ((List<?>)array).get(i));
        }
        return text.toString();
    }

    public static String observe(String[] args) {
        Object sentinel = JSONObject.NULL;
        JSONArray target = new JSONArray(2);
        target.put("seed").put(sentinel);
        String body;
        if (args[0].equals("alias")) {
            List<String> payload = new ArrayList<>(8);
            payload.add("a");
            Collection<Object> batch = Collections.<Object>singletonList(payload);
            boolean r1 = target.putAll(batch) == target;
            Object first = target.get(2);
            String before = values(first);
            payload.add("b");
            String after = values(first);
            boolean r2 = target.putAll(batch) == target;
            Object second = target.get(3), removed = target.remove(2);
            payload.clear();
            payload.add("c");
            body = "returns="+r1+"/"+r2+"|first="+before+"/"+after+"|sameInput="+(first==payload)+"/"+(second==payload)
                +"|sameSlots="+(first==second)+"|removedFirst="+(removed==first)+"|remaining="+target.length()+":"+values(target.get(2));
        } else if (args[0].equals("nan") || args[0].equals("infinity")) {
            Double bad = args[0].equals("nan") ? Double.NaN : Double.POSITIVE_INFINITY;
            String outcome;
            try {
                outcome = target.putAll(Arrays.asList("head", bad, "tail")) == target ? "return" : "different receiver";
            } catch (JSONException ex) {
                outcome = "throw("+ex.getClass().getName()+")";
            }
            StringBuilder visible = new StringBuilder();
            for (int i=2; i<target.length(); i++) {
                if (i>2) visible.append(',');
                visible.append(target.get(i));
            }
            int intermediate = target.length();
            target.putAll(Collections.singletonList("after"));
            body = "batch="+outcome+"|afterBatch="+intermediate+":"+visible+"|afterRecovery="+target.length()+":"+target.get(target.length()-1);
        } else if (args[0].equals("plain")) {
            boolean same = target.putAll(Arrays.asList("head", Integer.valueOf(7), sentinel)) == target;
            String added = target.get(2)+"/"+target.get(3)+"/"+(target.get(4)==sentinel);
            Object removed = target.remove(3);
            body = "returns="+same+"|added="+added+"|removed="+removed+"|left="+target.length()+"/"+target.get(2)+"/"+(target.get(3)==sentinel);
        } else {
            List<String> payload = new ArrayList<>(8);
            payload.add("a");
            JSONArray copy = new JSONArray(Collections.singletonList(payload));
            payload.add("later");
            target.putAll(Collections.singletonList(copy));
            body = "copy="+values(copy.get(0))+"|stored="+(target.get(2)==copy)+"|removed="+(target.remove(2)==copy)+"|left="+target.length();
        }
        return "base="+target.get(0)+"/"+(target.get(1)==sentinel)+"|"+body;
    }

    public static boolean change(boolean partialBatch) {
        return observe(new String[]{partialBatch ? "nan" : "alias"}).contains(partialBatch ? "throw(org.json.JSONException)" : "sameSlots=true");
    }
}
