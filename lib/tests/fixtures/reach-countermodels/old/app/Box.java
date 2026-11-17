package app;

/** The previous version declares a field x of its own, which hides Holder's and is never written. */
public class Box extends Holder {
    int x;
}
