import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import io.netty.buffer.UnpooledByteBufAllocator;
import reactor.core.publisher.Flux;
import org.springframework.core.io.buffer.*;

public class PublicCaller {
    static String write(boolean shortWrites, boolean async, String... parts) throws IOException {
        var factory = new NettyDataBufferFactory(UnpooledByteBufAllocator.DEFAULT);
        var buffers = new ArrayList<DataBuffer>();
        for (String s : parts) buffers.add(factory.allocateBuffer().write(s.getBytes(StandardCharsets.US_ASCII)));
        DataBuffer buffer = parts.length == 1 ? buffers.get(0) : factory.join(buffers);
        int components = 0;
        try (var it = buffer.readableByteBuffers()) {
            while (it.hasNext()) { it.next(); components++; }
        }
        Path path = Files.createTempFile(Path.of(System.getProperty("java.io.tmpdir")), "joined", ".bin");
        long emitted;
        if (async) {
            Files.writeString(path, "XX");
            try (var out = AsynchronousFileChannel.open(path, StandardOpenOption.WRITE)) {
                emitted = DataBufferUtils.write(Flux.just(buffer), out, 2).doOnNext(DataBufferUtils::release).count().block();
            }
        } else {
            try (var file = FileChannel.open(path, StandardOpenOption.WRITE)) {
                WritableByteChannel channel = new WritableByteChannel() {
                    public int write(ByteBuffer piece) throws IOException {
                        int limit = piece.limit();
                        if (shortWrites && piece.hasRemaining()) piece.limit(piece.position() + 1);
                        try { return file.write(piece); } finally { piece.limit(limit); }
                    }
                    public boolean isOpen() { return file.isOpen(); }
                    public void close() throws IOException { file.close(); }
                };
                emitted = DataBufferUtils.write(Flux.just(buffer), channel).doOnNext(DataBufferUtils::release).count().block();
            }
        }
        return "components=" + components + " emitted=" + emitted + " bytes=" + Files.readString(path, StandardCharsets.US_ASCII);
    }

    public static String observe(String[] args) throws IOException {
        return switch (args[0]) {
            case "joined" -> write(false, false, "foo","bar");
            case "single" -> write(false, false, "foobar");
            case "short" -> "sync " + write(true, false, "f","oob","ar") + " async " + write(false,true,"f","oob","ar");
            default -> throw new IllegalArgumentException(args[0]);
        };
    }
}
