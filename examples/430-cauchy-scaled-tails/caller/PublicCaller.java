import java.util.ArrayList;
import org.apache.commons.statistics.distribution.CauchyDistribution;

public class PublicCaller {
    static boolean near(double actual, double reference, double tolerance) {
        return Double.isFinite(actual) && Math.abs(actual / reference - 1) <= tolerance;
    }
    public static String observe(String[] args) {
        var d = CauchyDistribution.of(0.5, 2);
        if (args[0].equals("endpoints")) {
            var values = new ArrayList<String>();
            for (double p : new double[]{0, 0.5, 1})
                values.add(d.inverseCumulativeProbability(p) + "/" + d.inverseSurvivalProbability(p));
            return values.toString();
        }
        boolean scaled = args[0].equals("scaled");
        if (scaled) d = CauchyDistribution.of(0, Math.scalb(1.0, -100));
        double[] probabilities = scaled ? new double[]{Math.scalb(1.0, -1050)} : new double[]{1e-20, 1e-300};
        var values = new ArrayList<String>();
        boolean valid = true;
        for (double p : probabilities) {
            double target = scaled ? Math.scalb(1.0, 950) / Math.PI : 2 / (Math.PI * p);
            double lower = d.inverseCumulativeProbability(p), upper = d.inverseSurvivalProbability(p);
            double tolerance = scaled ? .01 : 1e-15;
            valid &= near(lower, -target, tolerance) && near(upper, target, tolerance);
            values.add(lower + "/" + upper);
        }
        return "within=" + valid + " values=" + values;
    }
}
