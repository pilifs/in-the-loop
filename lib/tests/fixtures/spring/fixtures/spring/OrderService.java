package fixtures.spring;

import jakarta.validation.constraints.Min;
import java.io.IOException;
import java.util.concurrent.CompletableFuture;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.scheduling.annotation.Async;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

/** A service whose advice does not always apply: each problem the boundary contract reports is here once. */
@Service
public class OrderService {
    @Value("${orders.limit:5}")
    int limit;

    @Transactional
    public Order place(String holdId) throws IOException {
        if (holdId.isEmpty()) {
            throw new IOException("no hold");
        }
        return new Order(holdId, 1);
    }

    @Transactional(propagation = Propagation.REQUIRES_NEW, rollbackFor = IOException.class)
    public void audited(String holdId) throws IOException {
        place(holdId);
    }

    @Transactional(rollbackForClassName = "IOException")
    public void named(String holdId) throws IOException, InterruptedException {
        place(holdId);
    }

    /** Calls its own advised method on `this`, directly and from a lambda: the proxy is not involved. */
    public Order placeAll(String holdId, int times) {
        Order last = null;
        try {
            for (int i = 0; i < times; i++) {
                last = this.place(holdId + i);
            }
            Runnable again = () -> {
                try {
                    place(holdId);
                } catch (IOException e) {
                    throw new IllegalStateException(e);
                }
            };
            again.run();
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
        return last;
    }

    /** The same call on another instance goes through that instance's proxy, so it is not reported. */
    public Order delegate(OrderService other, String holdId) throws IOException {
        return other.place(holdId);
    }

    @Transactional
    private void internal() {
    }

    @Transactional
    public static void utility() {
    }

    @Async
    public Order compute(String id) {
        return new Order(id, 2);
    }

    @Async
    public CompletableFuture<Order> computeLater(String id) {
        return CompletableFuture.completedFuture(new Order(id, 3));
    }

    @Cacheable("orders")
    public void warm() {
    }

    @Cacheable("orders")
    public Order cached(String id) {
        return new Order(id, 4);
    }

    @Scheduled(fixedDelayString = "${orders.sweep:1s}")
    public void sweep() {
    }

    @Scheduled(fixedDelay = 1000)
    public void sweepSome(int n) {
    }

    public void reserve(@Min(1) int seats) {
    }

    public void purge(String id) {
        internal();
    }
}
