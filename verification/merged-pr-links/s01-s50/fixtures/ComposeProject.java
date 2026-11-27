import java.io.*;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import org.springframework.boot.Banner;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.WebApplicationType;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.context.annotation.Configuration;

/** Private, loopback-published Compose service for one original Boot client fixture. */
public final class ComposeProject implements AutoCloseable {
    @Configuration(proxyBeanMethods = false) public static class App {}
    private final Path file;
    private final String project;

    ComposeProject(String service) throws Exception {
        Path work = Files.createTempDirectory("boot-compose-");
        project = "bootprobe" + UUID.randomUUID().toString().replace("-", "");
        file = work.resolve("compose.yaml");
        Files.writeString(file, "name: " + project + "\nservices:\n  fixture:\n" + service);
        try { command("up", "--detach", "--pull", "never", "--wait", "--wait-timeout", "45"); }
        catch (Exception failure) {
            try { close(); } catch (Exception cleanup) { failure.addSuppressed(cleanup); }
            throw failure;
        }
    }
    String command(String... args) throws Exception {
        var cmd = new ArrayList<>(List.of("docker", "compose", "--project-name", project, "--file", file.toString()));
        cmd.addAll(List.of(args));
        Path log = Files.createTempFile(file.getParent(), "compose-", ".log");
        Process p = new ProcessBuilder(cmd).directory(file.getParent().toFile()).redirectErrorStream(true).redirectOutput(log.toFile()).start();
        try {
            if (!p.waitFor(55, TimeUnit.SECONDS)) throw new IOException("compose " + args[0] + " timed out");
            if (p.exitValue() != 0) throw new IOException("compose " + args[0] + " exited " + p.exitValue());
            return Files.readString(log).strip();
        } finally { if (p.isAlive()) p.destroyForcibly(); }
    }
    ConfigurableApplicationContext context(String... extra) {
        var app = new SpringApplication(App.class);
        app.setWebApplicationType(WebApplicationType.NONE);
        app.setBannerMode(Banner.Mode.OFF);
        var args = new ArrayList<>(List.of("--spring.docker.compose.file=" + file, "--spring.docker.compose.lifecycle-management=none",
                "--spring.docker.compose.readiness.wait=never", "--spring.docker.compose.skip.in-tests=false"));
        args.addAll(List.of(extra));
        return app.run(args.toArray(String[]::new));
    }
    static int freeTcpPort() throws IOException {
        try (var socket = new ServerSocket(0,1,InetAddress.getLoopbackAddress())) { return socket.getLocalPort(); }
    }
    int port(int internal, String protocol) throws Exception {
        String binding = command("port", "--protocol", protocol, "fixture", Integer.toString(internal));
        int separator = binding.lastIndexOf(':');
        if (separator < 0 || !InetAddress.getByName(binding.substring(0, separator)).isLoopbackAddress())
            throw new IOException("service is not published on loopback");
        return Integer.parseInt(binding.substring(separator + 1));
    }
    public void close() throws Exception { command("down", "--volumes", "--timeout", "2"); }
}
