import com.fasterxml.jackson.databind.node.DoubleNode;
import com.fasterxml.jackson.databind.node.LongNode;

public final class RoundingBoundaries {
    public static void main(String[] args) {
        int differences = 0;
        for (long bin = 0; bin < 8192; bin++) {
            long midpoint = (1L << 54) + (bin << 31) + (1L << 30);
            for (int offset = -3; offset <= 3; offset++) {
                long input = midpoint + offset;
                LongNode node = new LongNode(input);
                boolean differs = node.floatValue() != new DoubleNode(node.doubleValue()).floatValue();
                if (!ConversionEquivalence.classified(input)) throw new AssertionError(input);
                if (differs) differences++;
            }
        }
        if (differences != 16384) throw new AssertionError(differences);
        LongNode witness = new LongNode(0x0040000040000001L);
        if (Float.floatToRawIntBits(witness.floatValue()) != 0x5a800001
            || Float.floatToRawIntBits(new DoubleNode(witness.doubleValue()).floatValue()) != 0x5a800000
            || Float.floatToRawIntBits(new DoubleNode(0x1p-150).floatValue()) != 0
            || Float.floatToRawIntBits(new DoubleNode(-0x1p-150).floatValue()) != 0x80000000) {
            throw new AssertionError("conversion witness bits");
        }
        System.out.println("8192 bins, 57344 inputs, 16384 disagreements; exact witness and signed zeros matched");
    }
}
