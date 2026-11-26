import java.io.*;
import org.springframework.http.*;

final class WireInput implements HttpInputMessage {
    private final HttpHeaders headers = new HttpHeaders();
    private final InputStream body;
    WireInput(byte[] bytes) {
        body = new ByteArrayInputStream(bytes);
        headers.setContentType(MediaType.parseMediaType("multipart/form-data;boundary=boundary"));
    }
    public HttpHeaders getHeaders() { return headers; }
    public InputStream getBody() { return body; }
}
