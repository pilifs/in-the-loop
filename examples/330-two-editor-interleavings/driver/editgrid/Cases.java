package editgrid;

import org.intheloop.controls.Grid;
import static org.intheloop.controls.Grid.fields;
import java.util.ArrayList;
import java.util.List;
public final class Cases {
    private static int nextId;
    static void visit(int[] steps,int position,int mask) {
        if(position==4) {
            int code=nextId++, actual=Editor.execute(steps);
            String[] labels={"read A","write A","read B","write B"};
            List<String> schedule=new ArrayList<>();for(int step:steps)schedule.add(labels[step]);
            Grid.row(code,fields("initial",0,"schedule",schedule),fields("revision",actual),fields("revision",Projection.revision(code)));
            return;
        }
        for(int i=0;i<4;i++) {
            if((mask&(1<<i))!=0 || (i%2==1 && (mask&(1<<(i-1)))==0))continue;
            steps[position]=i;visit(steps,position+1,mask|(1<<i));
        }
    }
    public static void main(String[] args){visit(new int[4],0,0);}
}
