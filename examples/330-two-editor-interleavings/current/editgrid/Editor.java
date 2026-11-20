package editgrid;

public final class Editor {
    public static int execute(int[] schedule) {
        int revision=0;
        int[] saved=new int[2];
        for(int step:schedule) {
            int editor=step/2;
            if(step%2==0)saved[editor]=revision;
            else revision=revision+1;
        }
        return revision;
    }
}
