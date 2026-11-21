import com.ctrip.framework.apollo.build.ApolloInjector;
import com.ctrip.framework.apollo.spi.ConfigFactory;
import com.ctrip.framework.apollo.spi.ConfigRegistry;
import com.ctrip.framework.apollo.spi.DefaultConfigFactoryManager;

public final class UpgradeProbe {
    public static String observe(String[] args) {
        ConfigRegistry registry = ApolloInjector.getInstance(ConfigRegistry.class);
        ConfigFactory value = ApolloInjector.getInstance(ConfigFactory.class);
        registry.register(args[0], value);
        ConfigFactory found = new DefaultConfigFactoryManager().getFactory(args[0]);
        return Boolean.toString(found == value);
    }
}
