import java.util.ArrayList;
import java.util.List;
import io.github.resilience4j.circuitbreaker.CircuitBreaker;
import io.github.resilience4j.circuitbreaker.IllegalStateTransitionException;

public class UpgradeProbe {
    public static String observe(String[] args) {
        CircuitBreaker breaker = CircuitBreaker.ofDefaults("events");
        List<String> events = new ArrayList<>();
        breaker.getEventPublisher().onStateTransition(e -> events.add(e.getStateTransition().name()));
        String commands = args[0].equals("invalid") ? "H" : args[0].equals("single") ? "OHC" : "OOHHCC";
        List<String> observed = new ArrayList<>();
        for (char command : commands.toCharArray()) {
            String termination = "ok";
            try {
                switch (command) {
                    case 'O': breaker.transitionToOpenState(); break;
                    case 'H': breaker.transitionToHalfOpenState(); break;
                    case 'C': breaker.transitionToClosedState(); break;
                    default: throw new AssertionError(command);
                }
            } catch (IllegalStateTransitionException e) { termination = e.getClass().getSimpleName(); }
            observed.add(termination + "/" + breaker.getState().name() + "/" + events.size());
        }
        return String.join("|", observed) + "@" + String.join(",",events);
    }
}
