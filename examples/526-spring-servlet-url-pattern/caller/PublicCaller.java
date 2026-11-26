import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.setup.MockMvcBuilders.standaloneSetup;

import org.springframework.stereotype.Controller;
import org.springframework.test.web.servlet.*;
import org.springframework.test.web.servlet.result.MockMvcResultMatchers;
import org.springframework.web.bind.annotation.RequestMapping;

public class PublicCaller {
    @Controller
    public static class Routes {
        @RequestMapping("/new")
        public String single() {
            return "redirect:/resource/12";
        }

        @RequestMapping("/nested")
        public String nested() {
            return "redirect:/resource/a/12";
        }

        @RequestMapping("/go")
        public String forward() {
            return "forward:/api/resource/1";
        }

        @RequestMapping("/query")
        public String query() {
            return "forward:/api/resource/1?arg=value";
        }
    }

    static String check(
            MockMvc mvc, String path, ResultMatcher matcher, String destination, boolean forward)
            throws Exception {
        ResultActions action = mvc.perform(get(path));
        org.springframework.mock.web.MockHttpServletResponse res = action.andReturn().getResponse();
        String actual = forward ? res.getForwardedUrl() : res.getRedirectedUrl();
        if (!destination.equals(actual)) return "destination=" + actual;
        try {
            action.andExpect(matcher);
            return "pass";
        } catch (AssertionError e) {
            return "reject";
        }
    }

    public static String observe(String[] args) throws Exception {
        MockMvc mvc = standaloneSetup(new Routes()).build();
        if (args[0].equals("exact")) {
            String dest = "/api/resource/1?arg=value";
            return dest
                    + ":"
                    + check(mvc, "/query", MockMvcResultMatchers.forwardedUrl(dest), dest, true)
                    + "/"
                    + check(
                            mvc,
                            "/query",
                            MockMvcResultMatchers.forwardedUrl("/api/resource/1Xarg=value"),
                            dest,
                            true);
        }
        try {
            ResultMatcher star = MockMvcResultMatchers.redirectedUrlPattern("/resource/*");
            String first = check(mvc, "/new", star, "/resource/12", false);
            if (args[0].equals("segments"))
                return first
                        + "/"
                        + check(mvc, "/nested", star, "/resource/a/12", false)
                        + "/"
                        + check(
                                mvc,
                                "/nested",
                                MockMvcResultMatchers.redirectedUrlPattern("/resource/**"),
                                "/resource/a/12",
                                false);
            return first
                    + "/"
                    + check(
                            mvc,
                            "/go",
                            MockMvcResultMatchers.forwardedUrlPattern("/api/**/?"),
                            "/api/resource/1",
                            true)
                    + "/"
                    + check(
                            mvc,
                            "/new",
                            MockMvcResultMatchers.redirectedUrlPattern("/other/*"),
                            "/resource/12",
                            false);
        } catch (NoSuchMethodError unavailable) {
            return "absent";
        }
    }
}
