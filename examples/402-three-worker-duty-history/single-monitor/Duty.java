public final class Duty {
    public interface Gates {
        void before(int actor, String operation, Board board);
        void after(int actor, String operation, Board board, boolean decision);
        void failed(int actor);
        void done(int actor);
    }
    public static final class Board {
        public int mask = 7, commits;
        final boolean force;
        Board(boolean force) { this.force=force; }
        private boolean neighborPresent(int actor) { return (mask & (1 << ((actor+1)%3))) != 0; }
        public synchronized boolean read(int actor) { return neighborPresent(actor); }
        public synchronized void commit(int actor, boolean yes) { finish(actor,yes); }
        // The caller of this method owns the board monitor throughout the update.
        private void finish(int actor, boolean yes) {
            if (yes) mask &= ~(1<<actor);
            commits++;
            if (commits==3) assert !force && mask!=0;
        }
        public synchronized boolean atomic(int actor) {
            boolean yes=neighborPresent(actor); finish(actor,yes); return yes;
        }
    }
    static void turn(Board board, int actor, boolean split, Gates gates) {
        boolean yes=false;
        try {
            if(!split) {
                if(gates!=null) gates.before(actor,"atomic",board);
                try { yes=board.atomic(actor); } finally { if(gates!=null)gates.after(actor,"atomic",board,yes); }
            } else {
                if(gates!=null) gates.before(actor,"read",board);
                try { yes=board.read(actor); } finally { if(gates!=null)gates.after(actor,"read",board,yes); }
                if(gates!=null) gates.before(actor,"commit",board);
                try { board.commit(actor,yes); } finally { if(gates!=null)gates.after(actor,"commit",board,yes); }
            }
        } catch (AssertionError failure) {
            if(gates==null) throw failure;
            gates.failed(actor);
        } finally { if(gates!=null)gates.done(actor); }
    }
    static final class Worker extends Thread {
        final Board board; final int actor; final boolean split; final Gates gates;
        Worker(Board b,int i,boolean split,Gates g){board=b;actor=i;this.split=split;gates=g;}
        public void run(){turn(board,actor,split,gates);}
    }
    public static Board execute(boolean split,boolean force,Gates gates) throws InterruptedException {
        Board b=new Board(force);
        Thread first=new Worker(b,0,split,gates),second=new Worker(b,1,split,gates);
        first.start(); second.start(); turn(b,2,split,gates);
        first.join();second.join();return b;
    }
    public static boolean atomic() throws Exception {return execute(false,false,null).mask!=0;}
    public static boolean split() throws Exception {return execute(true,false,null).mask!=0;}
    public static boolean atomicTerminal() throws Exception {return execute(false,true,null).mask!=0;}
    public static boolean splitTerminal() throws Exception {return execute(true,true,null).mask!=0;}
    // Each entry includes the terminal check in Board.commit, on whichever participant commits third.
}
