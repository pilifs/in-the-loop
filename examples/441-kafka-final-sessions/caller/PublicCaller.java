import java.time.Duration;
import java.util.*;
import org.apache.kafka.common.serialization.*;
import org.apache.kafka.common.utils.Bytes;
import org.apache.kafka.streams.*;
import org.apache.kafka.streams.kstream.*;
import org.apache.kafka.streams.state.SessionStore;
import org.apache.kafka.streams.test.ConsumerRecordFactory;

public class PublicCaller {
    static void output(KTable<Windowed<String>, Long> counts, String topic) {
        counts.toStream().map((k,v) -> KeyValue.pair(k.key()+"@"+k.window().start()+"-"+k.window().end(),v))
              .to(topic, Produced.with(Serdes.String(),Serdes.Long()));
    }
    static List<String> drain(TopologyTestDriver driver, String topic) {
        var result=new ArrayList<String>();
        for (;;) {
            var r=driver.readOutput(topic,new StringDeserializer(),new LongDeserializer());
            if (r==null) return result;
            result.add(r.key()+"="+r.value());
        }
    }
    static String run(boolean suppression, long delayed) {
        var builder=new StreamsBuilder();
        var counts=builder.stream("in",Consumed.with(Serdes.String(),Serdes.String()))
                .groupByKey(Grouped.with(Serdes.String(),Serdes.String()))
                .windowedBy(SessionWindows.with(Duration.ofMillis(5)).grace(Duration.ofMillis(2)))
                .count(Materialized.<String,Long,SessionStore<Bytes,byte[]>>as("counts").withCachingDisabled());
        output(counts,"raw");
        output(counts.suppress(Suppressed.untilWindowCloses(Suppressed.BufferConfig.unbounded())),"final");
        var config=new Properties();
        config.setProperty(StreamsConfig.APPLICATION_ID_CONFIG,"sessions");
        config.setProperty(StreamsConfig.BOOTSTRAP_SERVERS_CONFIG,"localhost:1");
        config.setProperty(StreamsConfig.STATE_DIR_CONFIG,java.nio.file.Path.of("state-"+delayed).toAbsolutePath().toString());
        config.setProperty(StreamsConfig.DEFAULT_KEY_SERDE_CLASS_CONFIG,Serdes.StringSerde.class.getName());
        config.setProperty(StreamsConfig.DEFAULT_VALUE_SERDE_CLASS_CONFIG,Serdes.StringSerde.class.getName());
        var factory=new ConsumerRecordFactory<>(new StringSerializer(),new StringSerializer());
        var keys=suppression ? List.of("A","T","A","U") : List.of("T","A");
        long[] times=suppression ? new long[]{0,3,5,25} : new long[]{10,delayed};
        var selected=new ArrayList<List<String>>();
        var trace=new ArrayList<String>();
        try (var driver=new TopologyTestDriver(builder.build(),config)) {
            for (int i=0; i<keys.size(); i++) {
                driver.pipeInput(factory.create("in",keys.get(i),"v",times[i]));
                var raw=drain(driver,"raw"); var end=drain(driver,"final");
                selected.add((suppression ? end : raw).stream().filter(s->s.startsWith("A@")).toList());
                trace.add(keys.get(i)+"@"+times[i]+":raw="+raw+",final="+end);
            }
        }
        return "selected="+selected+" trace="+trace;
    }
    public static String observe(String[] args) {
        if (args[0].equals("suppress")) return run(true,0);
        if (args[0].equals("neighbors")) return "older "+run(false,7)+" | newer "+run(false,9);
        return run(false,8);
    }
}
