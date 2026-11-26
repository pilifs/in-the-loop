import org.springframework.beans.factory.BeanFactory
import org.springframework.beans.factory.getBean

fun asText(factory: BeanFactory): PublicCaller.Box<String> = factory.getBean<PublicCaller.Box<String>>("count")
fun asNumber(factory: BeanFactory): PublicCaller.Box<Number> = factory.getBean<PublicCaller.Box<Number>>("count")
