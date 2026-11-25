package inner;

import org.junit.jupiter.api.*;

public class OuterA {
    @Nested
    @IndicativeSentencesGeneration(separator = " -> ", generator = DisplayNameGenerator.ReplaceUnderscores.class)
    class Ready_state {
        @Test
        void accepts_input() {}
    }
}
