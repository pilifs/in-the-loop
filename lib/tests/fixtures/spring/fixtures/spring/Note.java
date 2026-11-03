package fixtures.spring;

import com.fasterxml.jackson.annotation.JsonFormat;
import com.fasterxml.jackson.annotation.JsonIgnore;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.NotBlank;
import java.time.LocalDate;
import java.util.List;
import java.util.Optional;
import tools.jackson.databind.PropertyNamingStrategies;
import tools.jackson.databind.annotation.JsonNaming;

/** A bean the Jackson way: getters, fields, renames, ignores, a naming strategy. */
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
@JsonInclude(JsonInclude.Include.NON_NULL)
@JsonIgnoreProperties(value = {"secret"}, ignoreUnknown = true)
public class Note extends Base {
    public int count;
    private String more;
    @NotBlank private String author;
    private String token;

    public String getURL() { return "u"; }
    public String getCustomerName() { return "c"; }
    public String getAuthor() { return author; }
    public boolean isPaid() { return true; }
    public Boolean isOpen() { return true; }
    public Optional<String> getNote() { return Optional.empty(); }
    public List<Shape> getShapes() { return List.of(); }
    public Kind getKind() { return Kind.SMALL; }
    public Status getStatus() { return Status.OK; }
    public Empty getEmpty() { return new Empty(); }
    @JsonFormat(pattern = "yyyy-MM-dd") public LocalDate getDue() { return LocalDate.EPOCH; }
    @JsonProperty("extra") private String more() { return more; }
    @JsonIgnore public String getInternal() { return "i"; }
    public String getSecret() { return "s"; }
    public void setToken(String token) { this.token = token; }
    private String getPrivate() { return "p"; }
}
