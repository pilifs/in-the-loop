package net.terminalvalue.boxoffice.ticketing.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Duration;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.Test;

class HoldPolicyTest {

    private final HoldPolicy policy = new HoldPolicy(4, Duration.ofMinutes(5));

    @Test
    void acceptsOneToMaxDistinctSeats() {
        policy.validate(List.of("A1"));
        policy.validate(List.of("A1", "A2", "A3", "A4"));
    }

    @Test
    void rejectsEmptyOversizedAndDuplicateRequests() {
        assertThatThrownBy(() -> policy.validate(List.of())).isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> policy.validate(List.of("A1", "A2", "A3", "A4", "A5")))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> policy.validate(List.of("A1", "A1"))).isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void totalRefusesToOverflow() {
        assertThat(HoldPolicy.totalCents(4500, 3)).isEqualTo(13500);
        assertThatThrownBy(() -> HoldPolicy.totalCents(Long.MAX_VALUE, 2)).isInstanceOf(ArithmeticException.class);
    }

    @Test
    void groupsGetTenPercentOff() {
        assertThat(HoldPolicy.totalCents(4500, 5)).isEqualTo(22500);
        assertThat(HoldPolicy.totalCents(4500, 6)).isEqualTo(24300);
        assertThat(HoldPolicy.totalCents(4500, 8)).isEqualTo(32400);
    }

    @Test
    void anExpiredHoldFreesTheSeatBeforeTheSweeperRuns() {
        var now = Instant.parse("2026-10-24T12:00:00Z");
        assertThat(SeatStatus.isHoldable(SeatStatus.AVAILABLE, null, now)).isTrue();
        assertThat(SeatStatus.isHoldable(SeatStatus.HELD, now.plusSeconds(1), now)).isFalse();
        assertThat(SeatStatus.isHoldable(SeatStatus.HELD, now, now)).isTrue();
        assertThat(SeatStatus.isHoldable(SeatStatus.SOLD, null, now)).isFalse();
    }
}
