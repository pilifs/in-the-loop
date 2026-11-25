import java.nio.file.*;
import java.io.StringWriter;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.solr.request.LocalSolrQueryRequest;
import org.apache.solr.response.SolrQueryResponse;
import java.util.*;
import org.apache.solr.client.solrj.SolrQuery;
import org.apache.solr.client.solrj.embedded.EmbeddedSolrServer;
import org.apache.solr.common.SolrInputDocument;

public class PublicCaller {
    static final String[][] values = {{"Not Available","Low"}, {"Low","Medium"}, {"Medium","High"},
            {"High","Not Available"}, {"Not Available","Low"}, {"Low","Medium"}};

    static SolrInputDocument doc(int i, boolean repeat) {
        var d = new SolrInputDocument();
        d.addField("id", String.valueOf(i + 1));
        for (String label : values[i]) {
            d.addField("severity_mv", label);
            d.addField("labels_sds", label);
        }
        if (repeat) d.addField("severity_mv", "Low");
        return d;
    }
    public static String observe(String[] args) throws Exception {
        Path home = Path.of("fixtures/solr").toAbsolutePath();
        try (var server = new EmbeddedSolrServer(home, "fixture")) {
            for (int i = 0; i < values.length; i++) server.add(doc(i, false));
            server.commit();
            if (args[0].equals("duplicate")) {
                server.add(doc(0, true));
                server.commit();
            }
            String field = args[0].equals("string") ? "labels_sds" : "severity_mv";
            var q = new SolrQuery("*:*");
            q.setRows(0);
            q.setRequestHandler("/select");
            q.set("json.facet", "{f:{type:terms,method:enum,field:" + field + "}}");
            try (var core = server.getCoreContainer().getCore("fixture");
                 var request = new LocalSolrQueryRequest(core, q)) {
                var response = new SolrQueryResponse();
                core.execute(core.getRequestHandler("/select"), request, response);
                if (response.getException() != null) throw response.getException();
                var json = new StringWriter();
                core.getQueryResponseWriter("json").write(json, request, response);
                var facets = new ObjectMapper().readTree(json.toString()).required("facets");
                var counts = new TreeMap<String,Long>();
                for (var b : facets.required("f").required("buckets")) {
                    String label = b.required("val").textValue();
                    if (label == null || !b.required("count").isIntegralNumber() ||
                            counts.put(label, b.get("count").longValue()) != null) throw new IllegalStateException("invalid bucket " + b);
                }
                return "total=" + facets.required("count").longValue() + " " + counts;
            }
        }
    }
}
