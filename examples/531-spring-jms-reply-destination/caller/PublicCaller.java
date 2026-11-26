import jakarta.jms.*;

import org.apache.activemq.artemis.api.core.TransportConfiguration;
import org.apache.activemq.artemis.core.config.impl.ConfigurationImpl;
import org.apache.activemq.artemis.core.remoting.impl.invm.InVMAcceptorFactory;
import org.apache.activemq.artemis.core.server.ActiveMQServers;
import org.apache.activemq.artemis.jms.client.ActiveMQConnectionFactory;
import org.springframework.jms.core.JmsTemplate;

import java.util.concurrent.*;

public class PublicCaller {
    static String exchange(
            JmsTemplate template,
            ActiveMQConnectionFactory factory,
            Queue requests,
            Queue replies,
            String body,
            String mode)
            throws Exception {
        ExecutorService executor = Executors.newSingleThreadExecutor();
        try {
            Future<String> observed =
                    executor.submit(
                            () -> {
                                try (JMSContext ctx = factory.createContext();
                                        JMSConsumer receiver = ctx.createConsumer(requests)) {
                                    TextMessage request = (TextMessage) receiver.receive(4000);
                                    if (request == null) return "request timed out";
                                    Destination target = request.getJMSReplyTo();
                                    ctx.createProducer().send(target, "ack-" + request.getText());
                                    return target instanceof TemporaryQueue
                                            ? "temporary"
                                            : ((Queue) target).getQueueName();
                                }
                            });
            org.springframework.jms.core.MessageCreator create =
                    session -> session.createTextMessage(body);
            Message reply;
            if (mode.equals("temporary")) reply = template.sendAndReceive(requests, create);
            else if (mode.equals("names"))
                reply = template.sendAndReceive("requests", "replies", create);
            else reply = template.sendAndReceive(requests, replies, create);
            return observed.get(5, TimeUnit.SECONDS)
                    + ":"
                    + (reply instanceof TextMessage msg ? msg.getText() : "missing");
        } finally {
            executor.shutdownNow();
        }
    }

    public static String observe(String[] args) throws Exception {
        boolean temporary = args[0].equals("temporary");
        if (!temporary) {
            try {
                JmsTemplate.class.getMethod(
                        "sendAndReceive",
                        Destination.class,
                        Destination.class,
                        org.springframework.jms.core.MessageCreator.class);
            } catch (NoSuchMethodException unavailable) {
                return "absent";
            }
        }
        var config =
                new ConfigurationImpl()
                        .setPersistenceEnabled(false)
                        .setSecurityEnabled(false)
                        .addAcceptorConfiguration(
                                new TransportConfiguration(InVMAcceptorFactory.class.getName()));
        var broker = ActiveMQServers.newActiveMQServer(config);
        broker.start();
        try (var factory = new ActiveMQConnectionFactory("vm://0");
                JMSContext ctx = factory.createContext()) {
            var template = new JmsTemplate(factory);
            template.setReceiveTimeout(4000);
            Queue requests = ctx.createQueue("requests"), replies = ctx.createQueue("replies");
            String first =
                    exchange(
                            template,
                            factory,
                            requests,
                            replies,
                            "A",
                            temporary ? "temporary" : "objects");
            if (!args[0].equals("repeat")) return first;
            String second = exchange(template, factory, requests, replies, "B", "names");
            try (JMSConsumer consumer = ctx.createConsumer(replies)) {
                ctx.createProducer().send(replies, "C");
                return first + "/" + second + "/" + consumer.receiveBody(String.class, 4000);
            }
        } finally {
            broker.stop();
            org.apache.activemq.artemis.core.remoting.impl.invm.InVMConnector.resetThreadPool();
            org.apache.activemq.artemis.api.core.client.ActiveMQClient.clearThreadPools(
                    2, TimeUnit.SECONDS);
        }
    }
}
