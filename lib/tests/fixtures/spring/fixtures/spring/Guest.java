package fixtures.spring;

import jakarta.validation.constraints.NotBlank;

/** A nested request type: its constraint runs only where a @Valid leads into it. */
public record Guest(@NotBlank String name) {}
