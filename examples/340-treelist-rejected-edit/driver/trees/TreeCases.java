package trees;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import org.apache.commons.collections4.list.TreeList;
import org.intheloop.controls.Grid;
import static org.intheloop.controls.Grid.fields;

public final class TreeCases {
    static String next(Iterator<String> it) {
        try { return it.next(); } catch (RuntimeException e) { return "!" + e.getClass().getName(); }
    }

    public static void main(String[] args) {
        int id = 0;
        for (int n = 1; n <= 3; n++) {
            for (int bits = 0; bits < (1 << n); bits++) {
                List<String> values = new ArrayList<>();
                for (int i = n-1; i >= 0; i--) values.add((bits & (1 << i)) == 0 ? "A" : "B");
                for (String action : new String[]{"add","remove"}) {
                    for (int index : new int[]{-1,n+1,5,10}) {
                        TreeList<String> list = new TreeList<>(values);
                        Iterator<String> it = list.iterator();
                        String exception = "none";
                        try {
                            if (action.equals("add")) list.add(index, "X");
                            else list.remove(index);
                        } catch (RuntimeException e) { exception = e.getClass().getName(); }
                        Grid.row(id,fields("seed",values,"action",action,"index",index),
                                fields("exception",exception,"contents",new ArrayList<>(list),"existing",next(it),"fresh",next(list.iterator())),
                                fields("exception",Projection.exception(id),"contents",Projection.contents(id),
                                       "existing",Projection.existing(id),"fresh",Projection.fresh(id)));
                        id++;
                    }
                }
            }
        }
    }
}
