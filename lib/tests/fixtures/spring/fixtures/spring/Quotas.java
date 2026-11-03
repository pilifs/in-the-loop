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
        return remaining(tenant) + 1;
    }

    static int helper() {
        return 0;
    }
}
