import tools.jackson.dataformat.xml.*;

import java.io.*;
import java.util.*;

import javax.xml.stream.*;

public class PublicCaller {
    public static class DTO {
        public Map<String, String> badMap = new LinkedHashMap<>();
    }

    static XmlMapper mapper() {
        return XmlMapper.builder(
                        XmlFactory.builder()
                                .xmlNameProcessor(XmlNameProcessors.newAlwaysOnBase64Processor())
                                .build())
                .build();
    }

    public static String observe(String[] a) throws Exception {
        var dto = new DTO();
        switch (a[0]) {
            case "intent" -> dto.badMap.put("中文", "cjk");
            case "control" -> dto.badMap.put("abc", "ascii");
            default -> {
                dto.badMap.put("Ͽ", "below");
                dto.badMap.put("Ѐ", "at");
            }
        }
        String xml = mapper().writeValueAsString(dto);
        var stax = XMLInputFactory.newDefaultFactory().createXMLStreamReader(new StringReader(xml));
        Map<String, String> entries = new TreeMap<>();
        String name = null;
        try {
            while (stax.hasNext()) {
                int t = stax.next();
                if (t == XMLStreamConstants.START_ELEMENT) name = stax.getLocalName();
                if (t == XMLStreamConstants.CHARACTERS && !stax.isWhiteSpace())
                    entries.merge(name, stax.getText(), String::concat);
            }
        } finally {
            stax.close();
        }
        return entries + "/" + dto.badMap.equals(mapper().readValue(xml, DTO.class).badMap);
    }
}
