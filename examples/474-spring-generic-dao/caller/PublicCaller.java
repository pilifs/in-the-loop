import org.springframework.aop.support.AopUtils;
import org.springframework.beans.factory.BeanNotOfRequiredTypeException;
import org.springframework.cache.CacheManager;
import org.springframework.cache.annotation.*;
import org.springframework.cache.concurrent.ConcurrentMapCacheManager;
import org.springframework.context.annotation.*;
import org.springframework.core.ParameterizedTypeReference;

public class PublicCaller {
    public record User(String id) {}
    public record Order(String id) {}
    public interface BaseDao<T> { T persist(T value); }
    public static class Users implements BaseDao<User> {
        @CachePut(cacheNames="users", key="#p0.id") public User persist(User value) { return value; }
    }
    public static class Orders implements BaseDao<Order> {
        @CachePut(cacheNames="orders", key="#p0.id") public Order persist(Order value) { return value; }
    }
    @Configuration(proxyBeanMethods=false) @EnableCaching(proxyTargetClass=false)
    public static class Config {
        @Bean public BaseDao<User> userDao() { return new Users(); }
        @Bean public BaseDao<Order> orderDao() { return new Orders(); }
        @Bean public CacheManager cacheManager() { return new ConcurrentMapCacheManager("users","orders"); }
    }

    @SuppressWarnings("unchecked")
    public static String observe(String[] args) {
        try (var ctx = new AnnotationConfigApplicationContext(Config.class)) {
            var users = ctx.getBean(CacheManager.class).getCache("users");
            var orders = ctx.getBean(CacheManager.class).getCache("orders");
            var type = new ParameterizedTypeReference<BaseDao<User>>(){};
            var orderType = new ParameterizedTypeReference<BaseDao<Order>>(){};
            var beans = ctx.getBeanFactory();
            Object byName = beans.getBean("userDao");
            if (args[0].equals("mismatch")) {
                String wrong;
                try { beans.getBean("userDao",orderType); wrong = "accepted"; }
                catch (BeanNotOfRequiredTypeException e) { wrong = e.getClass().getSimpleName(); }
                try {
                    var d = beans.getBean("orderDao",orderType);
                    Order out = d.persist(new Order("9"));
                    return "wrong=" + wrong + " proxy=" + AopUtils.isJdkDynamicProxy(d) + " result=" + out.id()
                            + " orders=" + orders.get("9",Order.class).id() + " users=" + users.get("9");
                } catch (BeanNotOfRequiredTypeException e) { return "wrong=" + wrong + " order=" + e.getClass().getSimpleName(); }
            }
            boolean raw = args[0].equals("raw");
            try {
                BaseDao<User> dao = raw ? beans.getBean("userDao",BaseDao.class) : beans.getBean("userDao",type);
                User out = dao.persist(new User(raw ? "2" : "1"));
                User cached = users.get(out.id(),User.class);
                return "proxy=" + AopUtils.isJdkDynamicProxy(dao) + " same=" + (dao == byName)
                        + " result=" + out.id() + " users=" + (cached == null ? null : cached.id());
            } catch (BeanNotOfRequiredTypeException e) { return e.getClass().getSimpleName(); }
        }
    }
}
