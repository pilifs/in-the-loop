import javax.persistence.EntityManagerFactory;
import org.hibernate.SessionFactory;
import org.hibernate.resource.beans.container.spi.BeanContainer;
import org.hibernate.resource.beans.spi.*;
import org.springframework.beans.factory.support.RootBeanDefinition;
import org.springframework.context.support.GenericXmlApplicationContext;
import org.springframework.orm.jpa.hibernate.beans.*;

public class PublicCaller {
    public static class Known extends TestBean { }
    static class Options implements BeanContainer.LifecycleOptions {
        final boolean jpa;
        Options(boolean jpa) {this.jpa=jpa;}
        public boolean canUseCachedReferences() {return jpa;}
        public boolean useJpaCompliantCreation() {return jpa;}
    }
    static class Producer implements BeanInstanceProducer {
        int unnamed,named;
        Object produced;
        public <B>B produceBeanInstance(Class<B> type) {unnamed++; return create("unnamed",type);}
        public <B>B produceBeanInstance(String name,Class<B> type) {named++; return create(name,type);}
        <B>B create(String name,Class<B> type) {
            TestBean value;
            if (type==NoDefinitionInSpringContextTestBean.class) value=new NoDefinitionInSpringContextTestBean(name,BeanSource.FALLBACK);
            else {value=new Known(); value.setName(name);}
            produced=value;
            return type.cast(value);
        }
        String calls() {return " calls="+unnamed+"/"+named;}
    }
    public static String observe(String[] args) {
        String base="classpath:/org/springframework/orm/jpa/";
        try (GenericXmlApplicationContext ctx=new GenericXmlApplicationContext()) {
            ctx.load(base+"hibernate/hibernate-manager-native.xml",base+"memdb.xml",base+"inject.xml",
                    base+"hibernate/inject-hibernate-spring-bean-container-tests.xml");
            RootBeanDefinition known=new RootBeanDefinition(Known.class);
            known.setScope("prototype"); known.getPropertyValues().add("name","known");
            if (args[0].equals("decoy")) ctx.registerBeanDefinition("known",known);
            ctx.refresh();
            SessionFactory factory=ctx.getBean(EntityManagerFactory.class).unwrap(SessionFactory.class);
            BeanContainer container=factory.getSessionFactoryOptions().getServiceRegistry().requireService(ManagedBeanRegistry.class).getBeanContainer();
            Producer p=new Producer();
            Options nativeOptions=new Options(false);
            if (args[0].equals("injected")) {
                MultiplePrototypesInSpringContextTestBean bean=container.getBean("multiple-1",MultiplePrototypesInSpringContextTestBean.class,new Options(true),p).getBeanInstance();
                return bean.getName()+" context="+(bean.getApplicationContext()==ctx)+p.calls();
            }
            if (args[0].equals("fallback")) {
                NoDefinitionInSpringContextTestBean b=container.getBean("X",NoDefinitionInSpringContextTestBean.class,nativeOptions,p).getBeanInstance();
                return (b==p.produced ? b.getName() : "substituted")+p.calls();
            }
            if (args[0].equals("prototype")) {
                SinglePrototypeInSpringContextTestBean a=container.getBean(SinglePrototypeInSpringContextTestBean.class,nativeOptions,p).getBeanInstance();
                SinglePrototypeInSpringContextTestBean b=container.getBean(SinglePrototypeInSpringContextTestBean.class,nativeOptions,p).getBeanInstance();
                return a.getName()+"/"+b.getName()+" distinct="+(a!=b)+" contexts="+(a.getApplicationContext()==ctx && b.getApplicationContext()==ctx)+p.calls();
            }
            Known a=container.getBean("missing",Known.class,nativeOptions,p).getBeanInstance();
            Known b=container.getBean("known",Known.class,nativeOptions,p).getBeanInstance();
            return a.getName()+"/"+b.getName()+" distinct="+(a!=b && (p.named==0 || a==p.produced) && b.getApplicationContext()==ctx)+p.calls();
        }
    }
}
