import org.springframework.context.support.ClassPathXmlApplicationContext;
import pl.com.bottega.ecommerce.canonicalmodel.publishedlanguage.AggregateId;
import pl.com.bottega.ecommerce.sales.acceptancetests.AuthenticationTestHelper;
import pl.com.bottega.ecommerce.sales.application.api.command.OrderDetailsCommand;
import pl.com.bottega.ecommerce.sales.application.api.service.OfferChangedExcpetion;
import pl.com.bottega.ecommerce.sales.application.api.service.OrderingService;
import pl.com.bottega.ecommerce.sales.domain.offer.Offer;

public class UpgradeProbe {
    public static String observe(String[] input) {
        try (ClassPathXmlApplicationContext app = new ClassPathXmlApplicationContext()) {
            app.getEnvironment().setActiveProfiles("test");
            app.setConfigLocation("classpath:/functionalTestsContext.xml");
            app.refresh();
            app.getBean(AuthenticationTestHelper.class).asBuyer();
            OrderingService service = app.getBean(OrderingService.class);
            AggregateId order = service.createOrder();
            service.addProduct(order, new AggregateId("p1"), 1);
            service.addProduct(order, new AggregateId("p2"), 20);
            Offer offer = service.calculateOffer(order);
            if (input[0].equals("stale")) service.addProduct(order, new AggregateId("p2"), 30);
            try {
                service.confirm(order, new OrderDetailsCommand(), offer);
                return "confirmed";
            } catch (OfferChangedExcpetion e) {
                return "offer-changed";
            }
        }
    }
}
