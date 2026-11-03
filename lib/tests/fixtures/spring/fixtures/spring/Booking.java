package fixtures.spring;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.util.List;
import java.util.Optional;

/**
 * A request type with each way a constraint can fail to do what it says: a constraint on a type it has no validator
 * for, a null check on a primitive, a nested type reached without @Valid, constraints inside the type arguments, and
 * a constraint in a group that a plain @Valid does not run.
 */
public record Booking(
        @Size(max = 10) int seats,
        @NotNull int rows,
        List<@NotBlank String> labels,
        Guest guest,
        @Valid Guest payer,
        List<@Valid Guest> party,
        Optional<@Min(1) Integer> tier,
        @NotBlank(groups = OnCreate.class) String code) {}
