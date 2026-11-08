import java.io.File;
import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.net.URL;
import java.net.URLClassLoader;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Function;

/**
 * Runs each build of a fixture family on a grid of inputs and prints, for each build, the inputs on which it
 * differs from `before`: `java Conformance.java FAMILY CLASSES_ROOT`, where CLASSES_ROOT/NAME holds each build's
 * compiled classes. Every build gets the same environment (recording stubs, made with proxies in its own loader).
 */
public class Conformance {
    public static void main(String[] args) throws Exception {
        String family = args[0];
        File root = new File(args[1]);
        Map<String, Map<String, String>> runs = new LinkedHashMap<>();
        File[] builds = root.listFiles(File::isDirectory);
        java.util.Arrays.sort(builds);
        for (File build : builds) {
            ClassLoader loader = new URLClassLoader(new URL[] {build.toURI().toURL()}, null);
            Map<String, String> out = new LinkedHashMap<>();
            switch (family) {
                case "quote" -> quote(loader, out);
                case "throttle" -> throttle(loader, out);
                case "basket" -> basket(loader, out);
                default -> throw new IllegalArgumentException(family);
            }
            runs.put(build.getName(), out);
        }
        Map<String, String> before = runs.get("before");
        for (var e : runs.entrySet()) {
            if (e.getKey().equals("before")) {
                continue;
            }
            List<String> differs = new ArrayList<>();
            for (var c : before.entrySet()) {
                String other = e.getValue().get(c.getKey());
                if (!c.getValue().equals(other)) {
                    differs.add(c.getKey() + ": before " + c.getValue() + ", " + e.getKey() + " " + other);
                }
            }
            System.out.println(e.getKey() + ": " + before.size() + " cases, " + differs.size() + " differ");
            for (int i = 0; i < (System.getenv("ALL") != null ? differs.size() : Math.min(3, differs.size())); i++) { // ALL=1 prints every difference
                System.out.println("  " + differs.get(i));
            }
        }
    }

    /** What a call did: its result or exception's class, then what it left. */
    static String outcome(Callable call) {
        try {
            return "returns " + call.call();
        } catch (InvocationTargetException e) {
            return "throws " + e.getCause().getClass().getName();
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }

    interface Callable {
        Object call() throws Exception;
    }

    static Object stub(ClassLoader loader, String iface, java.lang.reflect.InvocationHandler h) throws Exception {
        Class<?> c = loader.loadClass(iface);
        return Proxy.newProxyInstance(loader, new Class<?>[] {c}, h);
    }

    static Object field(Object o, String name) throws Exception {
        Field f = o.getClass().getDeclaredField(name);
        f.setAccessible(true);
        return f.get(o);
    }

    static void quote(ClassLoader loader, Map<String, String> out) throws Exception {
        Class<?> service = loader.loadClass("quotes.QuoteService");
        Class<?> request = loader.loadClass("quotes.QuoteRequest");
        Class<?> offerClass = loader.loadClass("quotes.Offer");
        Constructor<?> makeService = service.getConstructors()[0];
        Constructor<?> makeRequest = request.getConstructor(String.class, int[].class);
        Constructor<?> makeOffer = offerClass.getConstructor(long.class, int.class);
        Method quote = service.getMethod("quote", request);
        Method offerQuote = service.getMethod("offerQuote", request);
        Method checked = service.getMethod("checked", request);
        long[] fees = {-7, 0, 5, 300};
        long[] floors = {0, 250, 10_000};
        String[] codes = {"VIP1", "VIP", "VI", "STD", "X", "", "\uD800V"};
        int[][] quantities = {{}, {1}, {2, 3}, {0}, {-1, 1}, {1, 1, 1}, {4, 0, 2, 1}, {Integer.MAX_VALUE, Integer.MAX_VALUE, Integer.MAX_VALUE}};
        // The rate a code gets: by code, the same for equal codes; -1 stands for RateUnavailable.
        Function<String, Long>[] rates = new Function[] {c -> 7L, c -> ((String) c).equals("STD") ? 3L : 11L, c -> ((String) c).isEmpty() ? -1L : 0L, c -> -1L, c -> -3L};
        long[][] offers = {null, {5, 0}, {3, 4}};
        for (long fee : fees) for (long floor : floors) for (int r = 0; r < rates.length; r++) for (int o = 0; o < offers.length; o++) {
            Function<String, Long> rate = rates[r];
            long[] offer = offers[o];
            List<String> events = new ArrayList<>();
            Object rateStub = stub(loader, "quotes.Rates", (p, m, a) -> {
                long v = rate.apply((String) a[0]);
                if (v == -1) {
                    throw (Throwable) loader.loadClass("quotes.RateUnavailable").getConstructor().newInstance();
                }
                return v;
            });
            Object offerStub = stub(loader, "quotes.Offers", (p, m, a) -> offer == null ? null : makeOffer.newInstance(offer[0], (int) offer[1]));
            Object eventStub = stub(loader, "quotes.Events", (p, m, a) -> {
                events.add(field(a[0], "code") + "/" + field(a[0], "amountCents"));
                return null;
            });
            Object s = makeService.newInstance(fee, floor, rateStub, offerStub, eventStub);
            for (String code : codes) for (int[] q : quantities) {
                Object req = makeRequest.newInstance(code, q);
                String at = "fee=" + fee + " floor=" + floor + " rates#" + r + " offer#" + o + " code=" + code + " q=" + java.util.Arrays.toString(q);
                events.clear();
                out.put("quote " + at, outcome(() -> quote.invoke(s, req)) + " events " + events);
                events.clear();
                out.put("offerQuote " + at, outcome(() -> offerQuote.invoke(s, req)) + " events " + events);
                out.put("checked " + at, outcome(() -> checked.invoke(s, req) == req ? "the request" : "another object"));
            }
        }
    }

    static void throttle(ClassLoader loader, Map<String, String> out) throws Exception {
        Class<?> throttle = loader.loadClass("throttle.Throttle");
        Constructor<?> make = throttle.getConstructor(int.class);
        Method take = throttle.getMethod("take", int.class);
        Method allows = throttle.getMethod("allows", int.class);
        int[] setups = {-1, 0, 1, 2, 5, Integer.MAX_VALUE};
        for (int capacity : new int[] {-1, 1, 2, 5, Integer.MAX_VALUE}) for (int n : new int[] {-1, 0, 1, 2, 3, 4, 5, 6, Integer.MAX_VALUE}) {
            // No setup: the constructor-only domain.
            out.put("capacity=" + capacity + " allows(" + n + ")", outcome(() -> allows.invoke(make.newInstance(capacity), n)));
            for (int k : setups) {
                out.put("capacity=" + capacity + " take(" + k + ") allows(" + n + ")", outcome(() -> {
                    Object t = make.newInstance(capacity);
                    take.invoke(t, k);
                    return allows.invoke(t, n);
                }));
            }
        }
    }

    static void basket(ClassLoader loader, Map<String, String> out) throws Exception {
        Class<?> line = loader.loadClass("basket.Line");
        Class<?> basket = loader.loadClass("basket.Basket");
        Constructor<?> make = line.getConstructor(long.class, int.class);
        Method total = basket.getMethod("total", List.class);
        Method first = basket.getMethod("first", List.class);
        Method clearAll = basket.getMethod("clearAll", List.class);
        String[] shapes = {"", "a", "ab", "aa", "ba", "abc", "aba"};
        for (String shape : shapes) for (int variant = 0; variant < 2; variant++) {
            int v = variant;
            Function<Boolean, List<Object>> list = fresh -> {
                try {
                    Object[] made = {make.newInstance(5L + v, 2), make.newInstance(-3L, 4 + v), make.newInstance(7L, 0)};
                    List<Object> elements = new ArrayList<>();
                    for (char c : shape.toCharArray()) {
                        elements.add(made[c - 'a']);
                    }
                    return List.copyOf(elements);
                } catch (Exception e) {
                    throw new RuntimeException(e);
                }
            };
            String at = "[" + shape + "] #" + v;
            out.put("total " + at, outcome(() -> total.invoke(null, list.apply(true))));
            out.put("first " + at, outcome(() -> {
                List<Object> l = list.apply(true);
                Object f = first.invoke(null, l);
                return f == null ? "null" : (f == l.get(0) ? "the first element" : "another object") + " " + field(f, "unitCents") + "x" + field(f, "quantity");
            }));
            out.put("clearAll " + at, outcome(() -> {
                List<Object> l = list.apply(true);
                Object r = clearAll.invoke(null, l);
                List<Object> left = new ArrayList<>();
                for (Object e : l) {
                    left.add(field(e, "quantity"));
                }
                return r + " leaving " + left;
            }));
        }
        out.put("total of null", outcome(() -> total.invoke(null, (Object) null)));
    }
}
