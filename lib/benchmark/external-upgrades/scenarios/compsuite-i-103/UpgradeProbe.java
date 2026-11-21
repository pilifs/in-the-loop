import com.alibaba.nacos.api.common.Constants;
import com.alibaba.nacos.api.config.ConfigService;
import com.alibaba.nacos.api.NacosFactory;
import com.alibaba.nacos.client.utils.ParamUtil;
import com.alibaba.nacos.embedded.web.server.NacosConfigHttpHandler;
import com.alibaba.nacos.spring.beans.factory.annotation.*;
import com.alibaba.nacos.spring.core.env.AnnotationNacosPropertySourceBuilder;
import com.alibaba.nacos.spring.core.env.NacosPropertySourcePostProcessor;
import com.alibaba.nacos.spring.context.annotation.config.NacosPropertySource;
import com.alibaba.nacos.spring.context.annotation.config.NacosPropertySources;
import com.alibaba.nacos.spring.test.TestApplicationHolder;
import com.alibaba.nacos.spring.test.TestConfiguration;
import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.util.*;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;
import org.springframework.context.support.AbstractApplicationContext;
import org.springframework.core.env.ConfigurableEnvironment;

public final class UpgradeProbe {
    @NacosPropertySources({
        @NacosPropertySource(name="second", dataId="testDataId", first=true),
        @NacosPropertySource(name="first", dataId="testDataId", first=true)
    })
    static class Settings {}

    public static String observe(String[] input) throws Exception {
        System.setProperty("nacos.standalone", "true");
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        NacosConfigHttpHandler handler = new NacosConfigHttpHandler();
        Map<String,String> original = new HashMap<>();
        original.put("dataId", "testDataId");
        original.put("group", Constants.DEFAULT_GROUP);
        original.put("content", "user.name=" + input[0]);
        handler.cacheConfig(original);
        String address = "127.0.0.1:" + server.getAddress().getPort();
        System.setProperty("server.addr", address);
        server.createContext("/" + ParamUtil.getDefaultContextPath() + Constants.CONFIG_CONTROLLER_PATH, handler);
        handler.init();
        server.start();
        try (AnnotationConfigApplicationContext context = new AnnotationConfigApplicationContext()) {
            ConfigService service = NacosFactory.createConfigService(address);
            context.getBeanFactory().registerSingleton(TestConfiguration.CONFIG_SERVICE_BEAN_NAME, service);
            context.register(AnnotationNacosInjectedBeanPostProcessor.class, NacosPropertySourcePostProcessor.class,
                    ConfigServiceBeanBuilder.class, AnnotationNacosPropertySourceBuilder.class,
                    TestConfiguration.class, TestApplicationHolder.class, Settings.class);
            ((AbstractApplicationContext)context).refresh();
            ConfigurableEnvironment env = context.getEnvironment();
            return env.getPropertySources().iterator().next().getName() + "/" + env.getProperty("user.name");
        } finally {
            server.stop(0);
            handler.destroy();
        }
    }
}
