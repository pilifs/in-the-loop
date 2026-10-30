package net.terminalvalue.contracts.fixtures;

/** Small methods with known verdicts, for testing the verifier. */
public final class TrafficLight {

    public enum Light { RED, AMBER, GREEN }

    public sealed interface Command permits Next, Hold {}

    public record Next() implements Command {}

    public record Hold(boolean flashing) implements Command {}

    public interface Sensor {
        int read();
    }

    private static final Sensor SENSOR = () -> 1;
    private static int steps;

    private TrafficLight() {}

    /** Pure, with a finite domain: verifiable. */
    public static Light step(Light light, Command command) {
        return switch (command) {
            case Next _ -> switch (light) {
                case RED -> Light.GREEN;
                case GREEN -> Light.AMBER;
                case AMBER -> Light.RED;
            };
            case Hold hold -> hold.flashing() ? Light.AMBER : light;
        };
    }

    /** Writes a static field. */
    public static Light counting(Light light) {
        steps++;
        return light;
    }

    /** Reads the clock. */
    public static boolean night(Light light) {
        return System.nanoTime() % 2 == 0;
    }

    /** Calls an interface whose implementations are not known. */
    public static int sensed(Light light) {
        return SENSOR.read();
    }

    /** Pure, but an int has too many values to enumerate. */
    public static int doubled(int x) {
        return 2 * x;
    }
}
