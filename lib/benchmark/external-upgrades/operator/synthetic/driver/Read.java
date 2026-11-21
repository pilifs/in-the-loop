public final class Read {
    public static void main(String[] args) {
        int n = Integer.parseInt(args[0]);
        System.out.println("{\"input\":\"" + args[0] + "\",\"result\":" + neutral.Counter.increment(n) + "}");
    }
}
