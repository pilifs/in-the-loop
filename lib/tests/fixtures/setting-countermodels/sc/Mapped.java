package sc;

import java.util.Optional;

/** Reads a system property through a method reference that Optional calls: the read's caller is a JDK class. */
public class Mapped {
    public static final String VALUE = Optional.of("sc.value").map(System::getProperty).orElse("absent");
}
