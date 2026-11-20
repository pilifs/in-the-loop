package optionalgrid;

import java.util.Optional;

public final class Choice {
    public static int choose(Optional<Integer> value,Fallback fallback) {
        return value.isPresent() ? value.get() : fallback.get();
    }
}
