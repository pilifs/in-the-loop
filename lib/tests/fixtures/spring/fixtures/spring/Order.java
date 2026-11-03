package fixtures.spring;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;

/** A request and response body: its constraints are shown on its wire properties. */
public record Order(@NotBlank String id, @Min(1) int seats) {}
