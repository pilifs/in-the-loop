package net.terminalvalue.boxoffice.ticketing.api;

import net.terminalvalue.boxoffice.ticketing.app.HoldService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

@RestController
class HoldController {

    private final HoldService holds;

    HoldController(HoldService holds) {
        this.holds = holds;
    }

    @GetMapping("/holds/{id}")
    ConcertController.Hold get(@PathVariable String id) {
        return ConcertController.Hold.of(holds.get(id));
    }
}
