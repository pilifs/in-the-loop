import java.util.ArrayList;
import org.eclipse.rdf4j.repository.RepositoryConnection;
import org.eclipse.rdf4j.repository.sail.SailRepository;
import org.eclipse.rdf4j.sail.memory.MemoryStore;

public class PublicCaller {
    static final String WHERE = " WHERE { ?x <urn:p> ?v }";
    static final String GROUPED = "SELECT ?x (MAX(?v) AS ?m)" + WHERE + " GROUP BY ?x";
    static String query(RepositoryConnection c, String sql, boolean markers) {
        var values = new ArrayList<String>();
        try (var cursor = c.prepareTupleQuery(sql).evaluate()) {
            while (cursor.hasNext()) {
                var row = cursor.next();
                values.add(markers ? row.getValue("marker").stringValue() :
                        "x=" + row.hasBinding("x") + ",m=" + row.hasBinding("m"));
            }
            values.sort(null);
            return values + " eof=" + !cursor.hasNext();
        }
    }
    public static String observe(String[] args) {
        var repo = new SailRepository(new MemoryStore());
        repo.init();
        try (var c = repo.getConnection()) {
            if (args[0].equals("join")) {
                String sql = "SELECT ?marker WHERE { VALUES ?marker { \"a\" \"b\" } { " + GROUPED + " } }";
                var vf = c.getValueFactory();
                var s = vf.createIRI("urn:s");
                c.add(s, vf.createIRI("urn:other"), vf.createLiteral(7));
                String before = query(c, sql, true);
                c.add(s, vf.createIRI("urn:p"), vf.createLiteral(7));
                return before + " | " + query(c, sql, true);
            }
            return query(c, args[0].equals("implicit") ? "SELECT (MAX(?v) AS ?m)" + WHERE : GROUPED, false);
        } finally { repo.shutDown(); }
    }
}
