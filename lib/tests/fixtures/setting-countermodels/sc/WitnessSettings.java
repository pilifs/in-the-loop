package sc;

public final class WitnessSettings {
    private static final class Setting {
        static final String value = System.getProperty("itloop.receiver.witness.unset");
    }

    public static boolean failsOnBoth(int input) {
        return Setting.value == null ? input != 7 : input != 7 || Setting.value.isEmpty();
    }
    public static boolean failsOnlyInProposal(int input) {
        return Setting.value == null || Setting.value.isEmpty() || input != 7;
    }
    public static boolean holdsOnlyInProposal(int input) {
        return Setting.value != null || input != 7;
    }
}
