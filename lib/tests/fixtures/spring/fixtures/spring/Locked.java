package fixtures.spring;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** A final class cannot be subclassed by the CGLIB proxy, so its advice never runs. */
@Service
public final class Locked {
    @Transactional
    public void run() {
    }
}
