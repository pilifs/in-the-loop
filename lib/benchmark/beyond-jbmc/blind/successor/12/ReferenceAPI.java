import org.sejda.model.parameter.SetMetadataParameters;

public final class ReferenceAPI {
    public static long primary(int n) {
        SetMetadataParameters p = new SetMetadataParameters();
        p.setUpdateCreatorProducerModifiedDate(n == 1);
        try { return p.isUpdateProducerModifiedDate() ? 1 : 0; }
        catch (NoSuchMethodError expected) { return -1; }
    }
    public static long control(int n) {
        SetMetadataParameters p = new SetMetadataParameters();
        p.put("title", "entry");
        return "entry".equals(p.getMetadata().get("title")) ? 1 : 0;
    }
}
