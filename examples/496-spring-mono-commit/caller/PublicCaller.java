import java.sql.*;
import java.util.*;
import java.util.concurrent.atomic.*;
import reactor.core.publisher.*;
import org.springframework.transaction.*;
import org.springframework.transaction.reactive.TransactionalOperator;
import org.springframework.transaction.support.DefaultTransactionDefinition;

public class PublicCaller {
    static final String URL="jdbc:h2:mem:commit;DB_CLOSE_DELAY=-1";
    static class Tx implements ReactiveTransaction {
        Connection connection;
        boolean rollbackOnly, complete;
        public boolean isNewTransaction() {return true;}
        public boolean isRollbackOnly() {return rollbackOnly;}
        public void setRollbackOnly() {rollbackOnly=true;}
        public boolean isCompleted() {return complete;}
    }
    static class Manager implements ReactiveTransactionManager {
        final MonoProcessor<Void> gate=MonoProcessor.create();
        Tx current;
        final boolean useDatabase;
        int commits, rollbacks;
        Manager(boolean db) {useDatabase=db;}
        public Mono<ReactiveTransaction> getReactiveTransaction(TransactionDefinition definition) {
            return Mono.fromCallable(() -> {
                current=new Tx();
                if (useDatabase) {current.connection=DriverManager.getConnection(URL); current.connection.setAutoCommit(false);}
                return current;
            });
        }
        public Mono<Void> commit(ReactiveTransaction t) {
            Tx tx=(Tx)t;
            return Mono.defer(() -> {
                commits++;
                return gate.then(Mono.fromRunnable(() -> {
                    try { if (useDatabase) {tx.connection.commit(); tx.connection.close();} }
                    catch (SQLException e) {throw new IllegalStateException(e);}
                    tx.complete=true;
                }));
            });
        }
        public Mono<Void> rollback(ReactiveTransaction t) {
            return Mono.fromRunnable(() -> {rollbacks++; ((Tx)t).complete=true;});
        }
    }
    static int count() {
        try (var c=DriverManager.getConnection(URL); var s=c.createStatement()) {
            c.setTransactionIsolation(Connection.TRANSACTION_READ_COMMITTED);
            try (var r=s.executeQuery("select count(*) from ledger where id=37")) { r.next(); return r.getInt(1); }
        } catch (SQLException e) {throw new IllegalStateException(e);}
    }
    public static String observe(String[] args) throws Exception {
        boolean db=args[0].equals("visible");
        var manager=new Manager(db);
        var operator=TransactionalOperator.create(manager,new DefaultTransactionDefinition());
        var values=new ArrayList<Integer>();
        var marker=new IllegalStateException("application");
        var error=new AtomicReference<Throwable>();
        var complete=new AtomicBoolean();
        var cancelled=new AtomicBoolean();
        var visible=new AtomicInteger(-1);
        Mono<Integer> work=Mono.just(7);
        if (db) {
            try (var c=DriverManager.getConnection(URL); var s=c.createStatement()) {s.execute("create table ledger(id integer primary key)");}
            if (count()!=0) throw new AssertionError("initial row");
            work=Mono.fromCallable(() -> {
                try (var s=manager.current.connection.createStatement()) {return s.executeUpdate("insert into ledger values(37)");}
            });
        } else if (args[0].equals("error")) work=Mono.error(marker);
        operator.transactional(work.doOnCancel(() -> cancelled.set(true))).subscribe(values::add,error::set,() -> {
            complete.set(true);
            if (db) visible.set(count());
        });
        boolean early=complete.get();
        manager.gate.onComplete();
        if (args[0].equals("error")) return "marker=" + (error.get()==marker) + " values=" + values
                + " commits=" + manager.commits + " rollbacks=" + manager.rollbacks;
        if (error.get()!=null) throw new AssertionError(error.get());
        if (db) return "count=" + values.get(0) + " visibleAtCompletion=" + visible + " visibleAfterRelease=" + count();
        return "cancel=" + cancelled + " early=" + early + " values=" + values + " complete=" + complete
                + " commits=" + manager.commits + " rollbacks=" + manager.rollbacks;
    }
}
