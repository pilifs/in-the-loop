package tiling;

public final class Oracle {
    public static int exact(int n) {
        switch(n) {
            case 0: return 1;
            case 1: return 1;
            case 2: return 2;
            case 3: return 3;
            case 4: return 5;
            case 5: return 8;
            case 6: return 13;
            case 7: return 21;
            case 8: return 34;
            case 9: return 55;
            case 10: return 89;
            case 11: return 144;
            case 12: return 233;
            case 13: return 377;
            case 14: return 610;
            case 15: return 987;
            case 16: return 1597;
            case 17: return 2584;
            case 18: return 4181;
            default: throw new IllegalArgumentException();
        }
    }
    public static int parity(int n){return exact(n)%2;}
}
