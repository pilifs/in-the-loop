package fixtures.spring;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

/** Listeners bound to the publisher's transaction: one writes after the commit, one before it. */
@Component
public class TaskAudit {
    private final JdbcTemplate jdbc;

    public TaskAudit(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    /** After the commit nothing commits again: the insert is never committed. */
    @TransactionalEventListener
    public void created(TaskCreated event) {
        jdbc.update("insert into audit(id, at) values (?, now())", event.id());
    }

    /** Before the commit the write joins the transaction: fine. */
    @TransactionalEventListener(phase = TransactionPhase.BEFORE_COMMIT)
    public void creating(TaskCreated event) {
        jdbc.update("insert into audit(id, at) values (?, now())", event.id());
    }
}
