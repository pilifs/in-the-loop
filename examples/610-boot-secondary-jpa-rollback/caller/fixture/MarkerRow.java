package fixture;

import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

@Entity
@Table(name = "proof_marker")
public class MarkerRow {
    @Id private int id;
    protected MarkerRow() {}
    public MarkerRow(int id) { this.id = id; }
}
