package fixtures.spring;

import jakarta.validation.Valid;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** Three ways to take a constrained body: without @Valid, with @Valid, and with a group. */
@RestController
@RequestMapping("/bookings")
public class BookingsController {
    @PostMapping
    public Booking book(@RequestBody Booking request) {
        return request;
    }

    @PostMapping("/check")
    public Booking check(@Valid @RequestBody Booking request) {
        return request;
    }

    @PostMapping("/create")
    public Booking create(@Validated(OnCreate.class) @RequestBody Booking request) {
        return request;
    }
}
