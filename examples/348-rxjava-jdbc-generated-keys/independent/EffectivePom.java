import java.io.File;
import java.io.FileOutputStream;
import org.apache.maven.model.Dependency;
import org.apache.maven.model.Parent;
import org.apache.maven.model.Repository;
import org.apache.maven.model.building.DefaultModelBuildingRequest;
import org.apache.maven.model.building.FileModelSource;
import org.apache.maven.model.building.ModelBuilder;
import org.apache.maven.model.building.ModelBuildingRequest;
import org.apache.maven.model.building.ModelSource;
import org.apache.maven.model.io.xpp3.MavenXpp3Writer;
import org.apache.maven.model.resolution.ModelResolver;
import org.codehaus.plexus.DefaultContainerConfiguration;
import org.codehaus.plexus.DefaultPlexusContainer;
import org.codehaus.plexus.PlexusConstants;

/** Ask the pinned Maven distribution for its effective model, including its built-in lifecycle bindings. */
public final class EffectivePom implements ModelResolver {
    private final File parent;

    private EffectivePom(File parent) {
        this.parent = parent;
    }

    public ModelSource resolveModel(String group, String name, String version) {
        if (!"com.github.davidmoten:sonatype-parent:0.1".equals(group + ":" + name + ":" + version)) {
            throw new IllegalArgumentException("Unexpected external POM " + group + ":" + name + ":" + version);
        }
        return new FileModelSource(parent);
    }

    public ModelSource resolveModel(Parent p) {
        return resolveModel(p.getGroupId(), p.getArtifactId(), p.getVersion());
    }

    public ModelSource resolveModel(Dependency d) {
        return resolveModel(d.getGroupId(), d.getArtifactId(), d.getVersion());
    }

    public void addRepository(Repository repository) {}
    public void addRepository(Repository repository, boolean replace) {}
    public ModelResolver newCopy() { return this; }

    public static void main(String[] args) throws Exception {
        DefaultPlexusContainer container = new DefaultPlexusContainer(new DefaultContainerConfiguration()
                .setClassPathScanning(PlexusConstants.SCANNING_INDEX).setAutoWiring(true));
        try (FileOutputStream output = new FileOutputStream(args[2])) {
            ModelBuilder builder = container.lookup(ModelBuilder.class);
            DefaultModelBuildingRequest request = new DefaultModelBuildingRequest()
                    .setPomFile(new File(args[0]).getCanonicalFile())
                    .setModelResolver(new EffectivePom(new File(args[1])))
                    .setSystemProperties(System.getProperties()).setProcessPlugins(true)
                    .setValidationLevel(ModelBuildingRequest.VALIDATION_LEVEL_MAVEN_3_0);
            new MavenXpp3Writer().write(output, builder.build(request).getEffectiveModel());
        } finally {
            container.dispose();
        }
    }
}
