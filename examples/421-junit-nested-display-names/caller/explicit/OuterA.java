package explicit;

import org.junit.jupiter.api.*;

public class OuterA {
    @Nested
    @IndicativeSentencesGeneration(separator = " -> ", generator = DisplayNameGenerator.ReplaceUnderscores.class)
    class Ready_state {
        @Test
        @DisplayName("accepts the sample")
        void accepts_input() {}
    }
}
