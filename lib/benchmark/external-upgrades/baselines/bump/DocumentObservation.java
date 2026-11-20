package fr.pilato.elasticsearch.crawler.fs.tika;

import fr.pilato.elasticsearch.crawler.fs.beans.Doc;
import fr.pilato.elasticsearch.crawler.fs.settings.Fs;
import fr.pilato.elasticsearch.crawler.fs.settings.FsSettings;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.Base64;

/** Observe the original caller on the same two ordinary test-document resources as the named tests. */
public final class DocumentObservation {
    public static void main(String[] args) throws Exception {
        for (String filename : new String[]{"test.docx", "test.txt"}) {
            FsSettings settings = FsSettings.builder("bump-observation")
                    .setFs(Fs.builder().setRawMetadata(true).build()).build();
            Doc document = new Doc();
            TikaInstance.reloadTika();
            String path = "/documents/" + filename;
            try (InputStream contents = DocumentObservation.class.getResourceAsStream(path)) {
                if (contents == null) throw new IllegalStateException("missing " + filename);
                TikaDocParser.generate(settings, contents, filename, path, document, null, 0);
            }
            String text = document.getContent();
            System.out.println("BUMP_FIELD " + filename + " " + (text == null ? "NULL"
                    : "UTF8:" + Base64.getEncoder().encodeToString(text.getBytes(StandardCharsets.UTF_8))));
        }
        try {
            Class.forName("org.apache.poi.ooxml.extractor.POIXMLTextExtractor", false,
                    DocumentObservation.class.getClassLoader());
            System.out.println("BUMP_LINK loaded");
        } catch (LinkageError problem) {
            System.out.println("BUMP_LINK " + problem.getClass().getName() + " " + problem.getMessage());
        }
    }
}
