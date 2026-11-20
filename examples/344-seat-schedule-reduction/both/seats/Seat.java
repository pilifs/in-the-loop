package seats;

public final class Seat {
    int owner;
    public synchronized boolean reserve(int who, Audit journal) {
        if (owner != 0) {
            journal.append(-who);
            return false;
        }
        owner = who;
        journal.append(who);
        return true;
    }
}
