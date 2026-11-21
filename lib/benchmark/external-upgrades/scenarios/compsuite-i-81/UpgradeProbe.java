import org.togglz.core.Feature;
import org.togglz.core.activation.AbstractPropertyDrivenActivationStrategy;
import org.togglz.core.repository.FeatureState;
import org.togglz.deltaspike.TestConfigSourceProvider;
import org.togglz.deltaspike.activation.DeltaSpikePropertyActivationStrategy;

public final class UpgradeProbe {
    private enum Flag implements Feature { FEATURE_ONE }
    public static String observe(String[] input) {
        boolean enabled = Boolean.parseBoolean(input[0]);
        FeatureState state = new FeatureState(Flag.FEATURE_ONE, !enabled);
        AbstractPropertyDrivenActivationStrategy strategy = new DeltaSpikePropertyActivationStrategy();
        TestConfigSourceProvider.putProperty("togglz.FEATURE_ONE", input[0]);
        return Boolean.toString(strategy.isActive(state, null));
    }
}
