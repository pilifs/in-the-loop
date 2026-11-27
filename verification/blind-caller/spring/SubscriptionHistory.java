package trial;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executors;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.TimeUnit;
import org.reactivestreams.Subscriber;
import org.reactivestreams.Subscription;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.core.io.buffer.DataBuffer;
import org.springframework.core.io.buffer.DefaultDataBufferFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.codec.ServerSentEvent;
import org.springframework.web.reactive.function.client.ClientResponse;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.BaseSubscriber;
import reactor.core.publisher.Flux;
import reactor.core.publisher.FluxSink;
import reactor.core.publisher.Mono;

/** Disclosed scheduler exercise using local responses on the original Spring and Reactor releases. */
public final class SubscriptionHistory {
    private static final ExecutorService worker = Executors.newSingleThreadExecutor();

    static final class Ticket extends BaseSubscriber<ServerSentEvent<String>> {
        final List<String> signals = new ArrayList<>();
        final CountDownLatch terminal = new CountDownLatch(1);
        FluxSink<DataBuffer> source;
        protected void hookOnSubscribe(Subscription subscription) { request(Long.MAX_VALUE); }
        protected void hookOnNext(ServerSentEvent<String> event) {
            signals.add("event(" + event.data() + "," + (event.retry() == null ? "null" : event.retry().toMillis()) + ")");
        }
        protected void hookOnComplete() { signals.add("complete"); terminal.countDown(); }
        protected void hookOnCancel() { signals.add("cancel"); terminal.countDown(); }
        protected void hookOnError(Throwable error) {
            Throwable cause = error.getCause();
            signals.add("error(" + error.getClass().getName() + "," + (cause == null ? "null" : cause.getClass().getName()) + ")");
            terminal.countDown();
        }
    }

    static void registered(Ticket ticket, FluxSink<DataBuffer> source) { ticket.source = source; }

    static Ticket subscribe() {
        Ticket ticket = new Ticket();
        Flux<DataBuffer> bytes = Flux.create(sink -> {
            Ticket owner = sink.contextView().get(Ticket.class);
            if (owner.source == null) registered(owner,sink);
            else sink.complete(); // An exception builder rereading this one-shot body sees EOF.
        });
        WebClient client = WebClient.builder().exchangeFunction(request -> Mono.just(ClientResponse.create(HttpStatus.OK)
                .header("Content-Type","text/event-stream").body(bytes).build())).build();
        Flux<ServerSentEvent<String>> events = client.get().uri("http://localhost/observation").retrieve()
                .bodyToFlux(new ParameterizedTypeReference<ServerSentEvent<String>>() {});
        events.contextWrite(ctx -> ctx.put(Ticket.class, ticket)).subscribe((Subscriber<ServerSentEvent<String>>)ticket);
        if (ticket.source == null) throw new IllegalStateException("subscription did not install its original source");
        return ticket;
    }

    static final class Delivery implements Runnable {
        final Ticket ticket;
        final FluxSink<DataBuffer> source;
        final String body;
        final boolean complete;
        final CountDownLatch done = new CountDownLatch(1);
        Delivery(Ticket ticket, String body, boolean complete) {
            this.ticket = ticket;
            this.source = ticket.source;
            this.body = body;
            this.complete = complete;
        }
        public void run() {
            try { deliver(ticket, source, body, complete); }
            finally { done.countDown(); }
        }
        void await() throws InterruptedException {
            if (!done.await(15,TimeUnit.SECONDS)) throw new IllegalStateException("worker timeout");
        }
    }

    static void deliver(Ticket ticket, FluxSink<DataBuffer> source, String body, boolean complete) {
        source.next(DefaultDataBufferFactory.sharedInstance.wrap(body.getBytes(StandardCharsets.UTF_8)));
        if (complete) source.complete();
    }

    static void dispatch(Ticket ticket, FluxSink<DataBuffer> source, Delivery task) throws InterruptedException {
        worker.execute(task);
        task.await();
    }

    public static void main(String[] args) throws Exception {
        try {
            Ticket a = subscribe(), b = subscribe(), unrelated = subscribe();
            String same = "data:same\n\n";
            dispatch(a,a.source,new Delivery(a,same,false));
            dispatch(b,b.source,new Delivery(b,same,false));
            Delivery other = new Delivery(unrelated,same,true);
            worker.execute(other);
            other.await();
            b.cancel();
            dispatch(b,b.source,new Delivery(b,same,true));
            dispatch(a,a.source,new Delivery(a,"retry:none\ndata:last\n\n",true));
            if (!a.terminal.await(10,TimeUnit.SECONDS) || !b.terminal.await(10,TimeUnit.SECONDS)
                    || !unrelated.terminal.await(10,TimeUnit.SECONDS)) throw new IllegalStateException("missing terminal signal");
            System.out.println("A " + a.signals);
            System.out.println("B " + b.signals);
            System.out.println("unrelated " + unrelated.signals);
        } finally {
            worker.shutdownNow();
        }
    }
}
