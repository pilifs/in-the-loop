package queuegrid;

import org.intheloop.controls.Grid;
import static org.intheloop.controls.Grid.fields;

import java.util.Arrays;

public final class Cases {
    private static void visit(int[] commands, int code, int place) {
        BoundedQueue queue = new BoundedQueue();
        int[] responses = new int[commands.length];
        for (int i = 0; i < commands.length; i++) responses[i] = queue.apply(commands[i]);
        int[] values = new int[queue.size()];
        for (int i = 0; i < values.length; i++) values[i] = queue.at(i);
        Grid.row(code, fields("initial",new int[0],"commands",commands), fields("history",responses,"contents",values),
                fields("history",Projection.history(code),"contents",Projection.contents(code)));
        if (commands.length < 4) for (int op = 0; op < 3; op++) {
            int[] next = Arrays.copyOf(commands,commands.length+1);
            next[commands.length] = op;
            visit(next,code + (op+1)*place,place*3);
        }
    }
    public static void main(String[] args) { visit(new int[0],0,1); }
}
