package fixture.webflux;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Scanner;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.PropertyNamingStrategy;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.WebApplicationType;
import org.springframework.boot.autoconfigure.EnableAutoConfiguration;
import org.springframework.boot.autoconfigure.web.reactive.WebFluxAutoConfiguration;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.context.annotation.*;
import org.springframework.core.env.Environment;
import org.springframework.web.bind.annotation.*;

@Configuration
@EnableAutoConfiguration
@Import(PersonApplication.People.class)
public class PersonApplication {
    public static class Person {
        private String firstName;
        public Person() {}
        public Person(String name) { this.firstName = name; }
        public String getFirstName() { return firstName; }
        public void setFirstName(String name) { this.firstName = name; }
    }

    @RestController
    public static class People {
        @GetMapping(value="/person", produces="application/json") public Person person() { return new Person("Ada"); }
        @PostMapping(value="/person", consumes="application/json", produces="text/plain")
        public String receive(@RequestBody Person person) { return String.valueOf(person.getFirstName()); }
        @GetMapping(value="/fixed", produces="application/json") public byte[] fixed() {
            return "{\"first_name\":\"Mia\"}".getBytes(StandardCharsets.UTF_8);
        }
    }
    @Bean public ObjectMapper mapper(Environment env) {
        ObjectMapper mapper = new ObjectMapper();
        if (env.getProperty("fixture.snake", Boolean.class, true)) mapper.setPropertyNamingStrategy(PropertyNamingStrategy.SNAKE_CASE);
        return mapper;
    }
    static String request(int port, boolean post) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL("http://127.0.0.1:" + port + "/person").openConnection();
        c.setConnectTimeout(4000);
        c.setReadTimeout(4000);
        if (post) {
            c.setRequestMethod("POST");
            c.setRequestProperty("Content-Type", "application/json");
            c.setDoOutput(true);
            try (OutputStream out = c.getOutputStream()) { out.write("{\"first_name\":\"Lin\"}".getBytes(StandardCharsets.UTF_8)); }
        }
        try {
            int status = c.getResponseCode();
            if (status != 200) return Integer.toString(status);
            String body;
            try (Scanner s = new Scanner(c.getInputStream(), "UTF-8").useDelimiter("\\A")) { body = s.hasNext() ? s.next() : ""; }
            if (post) return status + ":" + body;
            com.fasterxml.jackson.databind.JsonNode json = new ObjectMapper().readTree(body);
            if (json.size() != 1) throw new IllegalStateException("expected one person field");
            String key = json.fieldNames().next();
            return status + ":" + key + "=" + json.get(key).asText();
        } finally { c.disconnect(); }
    }
    public static void main(String[] args) throws Exception {
        String history = args[0];
        Class<?> config = history.equals("challenge") ? Class.forName("fixture.webflux.MilestoneClients") : PersonApplication.class;
        SpringApplication app = new SpringApplication(config);
        app.setWebApplicationType(WebApplicationType.REACTIVE);
        try (ConfigurableApplicationContext ctx = app.run("--server.port=0","--server.address=127.0.0.1",
                "--fixture.snake=" + !history.equals("control"))) {
            int port = ctx.getEnvironment().getRequiredProperty("local.server.port",Integer.class);
            System.out.println("ORIGIN " + WebFluxAutoConfiguration.class.getProtectionDomain().getCodeSource().getLocation().toURI().getPath());
            String result;
            if (history.equals("challenge")) result = (String) config.getMethod("read",ConfigurableApplicationContext.class).invoke(null,ctx);
            else result = request(port,false) + (history.equals("intent") ? "/" + request(port,true) : "");
            System.out.println("OBS " + result);
        }
    }
}
