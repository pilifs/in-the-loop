import static org.intheloop.controls.Grid.*;

public final class Cases {
    public static void main(String[] args) throws Exception {
        row(0, fields("entry", "QueueFill#queue", "arguments", new String[]{"0"}),
                fields("holds", QueueFill.queue(0)), fields());
        row(1, fields("entry", "QueueFill#queue", "arguments", new String[]{"255"}),
                fields("holds", QueueFill.queue(255)), fields());
        row(2, fields("entry", "QueueFill#queue", "arguments", new String[]{"39"}),
                fields("holds", QueueFill.queue(39)), fields());
        row(3, fields("entry", "QueueFill#queue", "arguments", new String[]{"76"}),
                fields("holds", QueueFill.queue(76)), fields());
        row(4, fields("entry", "QueueFill#fullMeansOccupied", "arguments", new String[]{"255"}),
                fields("holds", QueueFill.fullMeansOccupied(255)), fields());
        row(5, fields("entry", "QueueFill#fullMeansOccupied", "arguments", new String[]{"0"}),
                fields("holds", QueueFill.fullMeansOccupied(0)), fields());
        row(6, fields("entry", "QueueFill#fill", "arguments", new String[]{"0"}),
                fields("holds", QueueFill.fill(0)), fields());
        row(7, fields("entry", "QueueFill#fill", "arguments", new String[]{"Integer.MIN_VALUE"}),
                fields("holds", QueueFill.fill(Integer.MIN_VALUE)), fields());
        row(8, fields("entry", "QueueFill#fill", "arguments", new String[]{"Integer.MAX_VALUE"}),
                fields("holds", QueueFill.fill(Integer.MAX_VALUE)), fields());
        row(9, fields("entry", "QueueFill#staleSurvives", "arguments", new String[]{"0"}),
                fields("holds", QueueFill.staleSurvives(0)), fields());
        row(10, fields("entry", "QueueFill#staleSurvives", "arguments", new String[]{"-1"}),
                fields("holds", QueueFill.staleSurvives(-1)), fields());
        row(11, fields("entry", "QueueFill#covariant", "arguments", new String[]{"true"}),
                fields("holds", QueueFill.covariant(true)), fields());
        row(12, fields("entry", "QueueFill#covariant", "arguments", new String[]{"false"}),
                fields("holds", QueueFill.covariant(false)), fields());
    }
}
