import org.jfree.chart.axis.NumberAxis;
import org.jfree.chart.plot.XYPlot;
import org.jfree.data.xy.XYSeriesCollection;

public class UpgradeProbe {
    private static XYPlot plot(NumberAxis first, NumberAxis second, boolean domain) {
        XYPlot plot = new XYPlot(new XYSeriesCollection(), domain ? first : new NumberAxis(), domain ? new NumberAxis() : first, null);
        if (second != null) {
            if (domain) plot.setDomainAxis(1, second); else plot.setRangeAxis(1, second);
        }
        plot.setDomainPannable(true);
        plot.setRangePannable(true);
        first.setRange(0, 10);
        if (second != null) second.setRange(0, 10);
        return plot;
    }
    private static String bounds(NumberAxis axis) { return axis.getLowerBound() + "," + axis.getUpperBound(); }
    public static String observe(String[] args) {
        System.setProperty("java.awt.headless", "true");
        boolean domain = args[0].equals("domain");
        NumberAxis a = new NumberAxis("a"), b = new NumberAxis("b"), x = new NumberAxis("x"), y = new NumberAxis("y");
        XYPlot pair = plot(a, b, domain), soloA = plot(x, null, domain), soloB = plot(y, null, domain);
        a.setInverted(args[1].equals("first")); x.setInverted(a.isInverted());
        b.setInverted(args[1].equals("second")); y.setInverted(b.isInverted());
        StringBuilder result = new StringBuilder();
        for (double step : new double[]{0.1, -0.1}) {
            for (XYPlot p : new XYPlot[]{pair, soloA, soloB}) {
                if (domain) p.panDomainAxes(step, null, null); else p.panRangeAxes(step, null, null);
            }
            if (result.length() > 0) result.append('|');
            result.append(bounds(a)).append('/').append(bounds(b)).append('/').append(bounds(x)).append('/').append(bounds(y));
        }
        return result.toString();
    }
}
