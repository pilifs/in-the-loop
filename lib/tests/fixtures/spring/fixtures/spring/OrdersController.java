package fixtures.spring;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Min;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestMethod;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/** The HTTP boundary of a service: every handler is an entry point, and the guards on it are the contract. */
@RestController
@RequestMapping("/orders")
public class OrdersController {
    private final OrderService service;

    public OrdersController(OrderService service) {
        this.service = service;
    }

    @PostMapping(consumes = "application/json")
    public Order place(@Valid @RequestBody Order request) {
        return service.placeAll(request.id(), 1);
    }

    @GetMapping("/{id}")
    public Order get(@PathVariable String id, @RequestParam(required = false) @Min(1) Integer version) {
        return new Order(id, version == null ? 0 : version);
    }

    @DeleteMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public void purge(@PathVariable String id) {
        service.purge(id);
    }

    @RequestMapping(method = {RequestMethod.GET, RequestMethod.HEAD}, path = {"/count", "/total"})
    public int count() {
        return 0;
    }

    /** Not a boundary: no framework annotation, so it is not in the contract. */
    public String describe() {
        return "orders";
    }
}
