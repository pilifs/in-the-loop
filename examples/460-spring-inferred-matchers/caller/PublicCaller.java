import java.net.URI;
import org.hamcrest.CoreMatchers;
import org.hamcrest.Matcher;
import org.springframework.http.HttpMethod;
import org.springframework.mock.http.client.MockClientHttpRequest;
import org.springframework.test.web.client.RequestMatcher;
import org.springframework.test.web.client.match.MockRestRequestMatchers;
import static org.hamcrest.CoreMatchers.equalTo;
import static org.hamcrest.Matchers.contains;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.*;

public class PublicCaller {
    static MockClientHttpRequest request(String tail) {
        MockClientHttpRequest r = new MockClientHttpRequest(HttpMethod.GET, URI.create("https://example.invalid/?q=a&q=" + tail));
        r.getHeaders().add("X-Choice", "a");
        r.getHeaders().add("X-Choice", tail);
        return r;
    }

    static String outcome(RequestMatcher matcher, MockClientHttpRequest request) throws Exception {
        try {
            matcher.match(request);
            return "pass";
        } catch (AssertionError e) {
            return "AssertionError";
        }
    }

    static String inferred(MockClientHttpRequest r) throws Exception {
        return outcome(header("X-Choice", equalTo("a")), r) + "/" + outcome(queryParam("q", equalTo("a")), r);
    }

    // Only the list factories have new names. The scalar calls above are compiled directly on each revision.
    static String lists(MockClientHttpRequest r) throws Exception {
        String[] results = new String[2];
        int i = 0;
        for (String name : new String[]{"headerList", "queryParamList"}) {
            try {
                var factory = MockRestRequestMatchers.class.getMethod(name, String.class, Matcher.class);
                var matcher = (RequestMatcher) factory.invoke(null, i == 0 ? "X-Choice" : "q", contains("a", "b"));
                results[i++] = outcome(matcher, r);
            } catch (NoSuchMethodException e) {
                results[i++] = "absent";
            }
        }
        return String.join("/", results);
    }

    public static String observe(String[] args) throws Exception {
        var ab = request("b");
        var ac = request("c");
        return switch (args[0]) {
            case "inferred" -> inferred(ab);
            case "typed" -> outcome(header("X-Choice", CoreMatchers.<String>equalTo("a")), ab)
                    + "/" + outcome(queryParam("q", CoreMatchers.<String>equalTo("a")), ab);
            case "tail" -> "scalar=" + inferred(ac) + " listAB=" + lists(ab) + " listAC=" + lists(ac);
            default -> throw new IllegalArgumentException(args[0]);
        };
    }
}
