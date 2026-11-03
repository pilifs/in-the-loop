package fixtures.spring;

import jakarta.validation.constraints.Positive;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.validation.annotation.Validated;

/** Class-level advice: every public method is transactional, and the constraints are enforced by @Validated. */
@Service
@Validated
@Transactional(readOnly = true)
public class Quotas {
    public int remaining(@Positive int tenant) {
        return tenant;
    }

    public int refill(int tenant) {
        return remaining(tenant) + quiet(tenant) + 1;
    }

    /** Not public: the proxy that validates does not see the call. */
    private int quiet(@Positive int tenant) {
        return tenant;
    }

    static int helper() {
        return 0;
    }
}
