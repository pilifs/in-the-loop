import java.util.*;
import org.apache.commons.pool2.*;
import org.apache.commons.pool2.impl.*;

public class PublicCaller {
    record Token(String id) {}
    static class Log {
        int made;
        final IllegalStateException failure = new IllegalStateException("fixture validation");
        final List<String> destroyed = new ArrayList<>();
        String mode;
        Token create() { return new Token(Character.toString('A' + made++)); }
        boolean validate() {
            if (mode.equals("throw")) throw failure;
            return !mode.equals("false");
        }
    }

    interface Pool extends AutoCloseable {
        Token borrow() throws Exception;
        void giveBack(Token t) throws Exception;
        void evict() throws Exception;
        int idle();
        int active();
    }
    static Pool ordinary(Log log) {
        var f = new BasePooledObjectFactory<Token>() {
            public Token create() { return log.create(); }
            public PooledObject<Token> wrap(Token t) { return new DefaultPooledObject<>(t); }
            public boolean validateObject(PooledObject<Token> p) { return log.validate(); }
            public void destroyObject(PooledObject<Token> p) { log.destroyed.add(p.getObject().id()); }
        };
        var pool = new GenericObjectPool<>(f);
        pool.setMaxTotal(1);
        configure(pool);
        return new Pool() {
            public Token borrow() throws Exception { return pool.borrowObject(); }
            public void giveBack(Token t) { pool.returnObject(t); }
            public void evict() throws Exception { pool.evict(); }
            public int idle() { return pool.getNumIdle(); }
            public int active() { return pool.getNumActive(); }
            public void close() { pool.close(); }
        };
    }
    static Pool keyed(Log log) {
        var f = new BaseKeyedPooledObjectFactory<String,Token>() {
            public Token create(String key) { return log.create(); }
            public PooledObject<Token> wrap(Token t) { return new DefaultPooledObject<>(t); }
            public boolean validateObject(String key, PooledObject<Token> p) { return log.validate(); }
            public void destroyObject(String key, PooledObject<Token> p) { log.destroyed.add(p.getObject().id()); }
        };
        var pool = new GenericKeyedObjectPool<>(f);
        pool.setMaxTotal(1);
        pool.setMaxTotalPerKey(1);
        configure(pool);
        return new Pool() {
            public Token borrow() throws Exception { return pool.borrowObject("one"); }
            public void giveBack(Token t) { pool.returnObject("one", t); }
            public void evict() throws Exception { pool.evict(); }
            public int idle() { return pool.getNumIdle("one"); }
            public int active() { return pool.getNumActive("one"); }
            public void close() { pool.close(); }
        };
    }
    static void configure(BaseGenericObjectPool<Token> pool) {
        pool.setBlockWhenExhausted(false);
        pool.setTestWhileIdle(true);
        pool.setNumTestsPerEvictionRun(1);
        pool.setEvictionPolicy((config, object, idle) -> false);
    }
    static String exercise(boolean keyed, String history) throws Exception {
        var log = new Log();
        try (Pool p = keyed ? keyed(log) : ordinary(log)) {
            var a = p.borrow();
            p.giveBack(a);
            log.mode = history.equals("false") ? "false" : "throw";
            String outcome = "normal";
            try { p.evict(); }
            catch (IllegalStateException e) { outcome = e == log.failure ? "same" : "different"; }
            String state = outcome + ", destroyed=" + log.destroyed + ", idle=" + p.idle() + ", active=" + p.active();
            if (history.equals("again")) {
                log.mode = "valid";
                try {
                    Token b = p.borrow();
                    p.giveBack(b);
                    state += "; borrowed=" + b.id() + " different=" + (a != b) + ", returned=" + p.idle() + "/" + p.active() + ", destroyed=" + log.destroyed;
                } catch (NoSuchElementException exhausted) { state += "; exhausted"; }
            }
            return state;
        }
    }
    public static String observe(String[] args) throws Exception {
        return "ordinary=" + exercise(false, args[0]) + "; keyed=" + exercise(true, args[0]);
    }
}
