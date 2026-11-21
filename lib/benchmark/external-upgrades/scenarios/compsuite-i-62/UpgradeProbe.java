import java.util.Arrays;
import java.util.List;
import org.springframework.context.support.ClassPathXmlApplicationContext;
import com.baidu.unbiz.fluentvalidator.dto.Car;
import com.baidu.unbiz.fluentvalidator.service.CarService;

public class UpgradeProbe {
    public static String observe(String[] input) {
        try (ClassPathXmlApplicationContext app = new ClassPathXmlApplicationContext("classpath*:applicationContext.xml")) {
            List<Car> cars = Arrays.asList(new Car("BMW", input[0], 5),
                    new Car("Benz", "NYCuuu", 2), new Car("Chevrolet", "LA1234", 7));
            List<Car> result = app.getBean(CarService.class).addCarsWithExcludeGroups(cars);
            return result.size() + "/" + result.get(0).getLicensePlate();
        }
    }
}
