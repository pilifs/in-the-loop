import java.lang.reflect.Proxy;
import io.r2dbc.spi.*;
import reactor.core.publisher.Mono;
import org.springframework.r2dbc.connection.*;
import org.springframework.transaction.reactive.TransactionalOperator;

public class PublicCaller {
    static class Provider implements ConnectionFactory {
        final String mode;
        final R2dbcBadGrammarException rollbackError=new R2dbcBadGrammarException("rollback");
        final R2dbcTimeoutException restoreError=new R2dbcTimeoutException("restore");
        boolean loaned;
        int commits,rollbacks,restores,closes;
        Provider(String mode) {this.mode=mode;}
        public ConnectionFactoryMetadata getMetadata() {return () -> "recording provider";}
        public Mono<Connection> create() {
            return Mono.fromCallable(() -> {
                if (loaned) throw new IllegalStateException("slot occupied");
                loaned=true;
                return (Connection)Proxy.newProxyInstance(Connection.class.getClassLoader(),new Class<?>[]{Connection.class},(self,m,a) -> {
                    switch (m.getName()) {
                        case "toString": return "physical connection";
                        case "hashCode": return System.identityHashCode(self);
                        case "equals": return self==a[0];
                        case "isAutoCommit": return true;
                        case "beginTransaction": case "setTransactionIsolationLevel": return Mono.empty();
                        case "commitTransaction": return Mono.fromRunnable(() -> commits++);
                        case "rollbackTransaction": return Mono.defer(() -> {rollbacks++; return mode.equals("slot") ? Mono.error(rollbackError) : Mono.empty();});
                        case "setAutoCommit": return Mono.defer(() -> {
                            if (Boolean.TRUE.equals(a[0])) {restores++; if (!mode.equals("success")) return Mono.error(restoreError);}
                            return Mono.empty();
                        });
                        case "close": return Mono.fromRunnable(() -> {closes++; loaned=false;});
                        default: throw new AssertionError(m);
                    }
                });
            });
        }
    }
    public static String observe(String[] args) {
        var p=new Provider(args[0]);
        var op=TransactionalOperator.create(new R2dbcTransactionManager(p));
        String status="ok";
        try {
            op.execute(tx -> args[0].equals("slot") ? Mono.error(new IllegalStateException("work")) : Mono.just("work")).then().block();
        } catch (RuntimeException e) {status=e.getClass().getSimpleName() + " cause=" + (e.getCause()==p.rollbackError);}
        String state=" commits=" + p.commits + " rollbacks=" + p.rollbacks + " restores=" + p.restores + " closes=" + p.closes;
        if (!args[0].equals("slot")) return status+state;
        try {
            Connection next=p.create().block();
            Mono.from(next.close()).block();
            return status+state+" next=true";
        } catch (IllegalStateException e) {return status+state+" next=false";}
    }
}
