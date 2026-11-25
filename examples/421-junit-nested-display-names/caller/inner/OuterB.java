package inner;

import org.junit.jupiter.api.*;

public class OuterB {
    @Nested
    @IndicativeSentencesGeneration(separator = " -> ", generator = DisplayNameGenerator.ReplaceUnderscores.class)
    class Ready_state {
        @Test
        void accepts_input() {}
    }
}
