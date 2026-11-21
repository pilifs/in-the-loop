import java.io.OutputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import org.apache.maven.model.Dependency;
import org.apache.maven.model.Parent;
import org.apache.maven.model.Repository;
import org.apache.maven.model.building.DefaultModelBuilderFactory;
import org.apache.maven.model.building.DefaultModelBuildingRequest;
import org.apache.maven.model.building.FileModelSource;
import org.apache.maven.model.building.ModelBuildingRequest;
import org.apache.maven.model.building.ModelSource;
import org.apache.maven.model.io.xpp3.MavenXpp3Writer;
import org.apache.maven.model.resolution.ModelResolver;
import org.apache.maven.model.resolution.UnresolvableModelException;

/** Run Maven's own effective model builder with an offline, coordinate-addressed POM repository. */
public final class EffectivePom implements ModelResolver {
    private final Path repository;

    private EffectivePom(Path repository) {
        this.repository = repository;
    }

    public ModelSource resolveModel(String group, String artifact, String version)
            throws UnresolvableModelException {
        Path pom = repository.resolve(group.replace('.', '/')).resolve(artifact).resolve(version)
                .resolve(artifact + "-" + version + ".pom");
        if (!Files.isRegularFile(pom)) {
            throw new UnresolvableModelException("Missing " + pom, group, artifact, version);
        }
        return new FileModelSource(pom.toFile());
    }

    public ModelSource resolveModel(Parent parent) throws UnresolvableModelException {
        return resolveModel(parent.getGroupId(), parent.getArtifactId(), parent.getVersion());
    }

    public ModelSource resolveModel(Dependency dependency) throws UnresolvableModelException {
        return resolveModel(dependency.getGroupId(), dependency.getArtifactId(), dependency.getVersion());
    }

    public void addRepository(Repository ignored) {}
    public void addRepository(Repository ignored, boolean replace) {}
    public ModelResolver newCopy() { return this; }

    public static void main(String[] args) throws Exception {
        DefaultModelBuildingRequest request = new DefaultModelBuildingRequest()
                .setPomFile(Path.of(args[0]).toFile())
                .setModelResolver(new EffectivePom(Path.of(args[1])))
                .setSystemProperties(System.getProperties())
                .setValidationLevel(ModelBuildingRequest.VALIDATION_LEVEL_MAVEN_3_0)
                .setProcessPlugins(true);
        var model = new DefaultModelBuilderFactory().newInstance().build(request).getEffectiveModel();
        try (OutputStream stream = Files.newOutputStream(Path.of(args[2]))) {
            new MavenXpp3Writer().write(stream, model);
        }
    }
}
