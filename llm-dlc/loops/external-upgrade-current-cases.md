# Current Java upgrade decisions

These reports cover all 32 registered callers. Each finite result applies to its stated inputs. The Derby comparison uses the original test environment.

## reflectasm · compsuite-i-38

**Upgrade** org.ow2.asm:asm `5.1` → `7.2`. [Original revisions](https://github.com/compsuite-team/reflectasm/compare/7cab65bb46ccd17b07ad05dd6b83d92a695477fc...5c636af1a65b92fa570582628a27aa1e7d29f24b)

**Caller-visible behavior** `com.esotericsoftware.reflectasm.MethodAccess#get`. Construct an interface method accessor and invoke replace on a populated concurrent map.

**Result** Changed. 1 of 2 inputs changed. Input 0 produced {"return": "one/2"} before and {"throws": "java.lang.IllegalArgumentException"} after. [Receipt](../../verification/external-upgrades/corpus-runs/v2-final-finite/01/compsuite-i-38.json)

**Scope** The original developer test expects the previous map value and two entries. Object declares no exported accessor methods in this adapter. The complete-module reference records both outcomes. The check uses the original runtime dependencies. V0 was open and V1 was changed.

**Review action** Review the changed return or exception before adopting the new pin.

## retrofit · compsuite-i-1

**Upgrade** com.squareup.wire:wire-runtime `2.2.0` → `3.0.2`. [Original revisions](https://github.com/compsuite-team/retrofit/compare/b8d593cf029652eb682434c0217ad92b5cbb005e...577716be23b960fe24b31b1edcdf6b01e88a692e)

**Caller-visible behavior** `retrofit2.converter.wire.WireResponseBodyConverter#convert`. Deserialize a serialized phone response and read the phone number.

**Result** Preserved. Both versions matched the independent expectations on all 2 inputs. [Receipt](../../verification/external-upgrades/corpus-runs/v2-final-finite/01/compsuite-i-1.json)

**Scope** The checked-in generated Phone message has a length-delimited string in protobuf field 1. The first body is byte-for-byte the historical developer test. The short-string companion uses the same wire rule. The check uses the original runtime dependencies. V0 was open and V1 was preserved.

**Review action** Keep the historical change open on this input domain.

## excel-streaming-reader · compsuite-i-70

**Upgrade** org.apache.poi:poi-ooxml `4.0.0` → `4.1.1`. [Original revisions](https://github.com/compsuite-team/excel-streaming-reader/compare/3188aa5ed02b43aee8732c9027728d47f10a4e03...eed036e11b5aecaeb5889fae26505e9409bdc438)

**Caller-visible behavior** `com.monitorjbl.xlsx.impl.StreamingCell#getCellStyle`. Read the style of an unformatted cell from the original spreadsheet.

**Result** Open. The old observer produced {"return": "1/NUMERIC/true"}. On the upgrade it stopped before the selected method. The JVM traced the escaping java.lang.IncompatibleClassChangeError to `org.apache.poi.openxml4j.opc.PackageRelationshipCollection#parseRelationshipsPart(Lorg/apache/poi/openxml4j/opc/PackagePart;)V` at line 303. The recorded cause ends in `java.lang.IncompatibleClassChangeError`. [Receipt](../../verification/external-upgrades/corpus-runs/v2-final-finite/01/compsuite-i-70.json)

**Scope** The original developer test requires exactly one worksheet, a numeric first cell and a non-null style. The input spreadsheet is unchanged in both Git revisions. The check uses the original runtime dependencies. V0 was open and V1 was open.

**Review action** Resolve the earlier failure and rerun the downstream operation.

## languagetool · compsuite-i-10

**Upgrade** org.apache.lucene:lucene-backward-codecs `5.5.4` → `8.3.1`. [Original revisions](https://github.com/compsuite-team/languagetool/compare/fe77e85a2f7b472ba71564821e7545025eeda242...d1263f08d7ad45e836e3169d0bdee01cbbebd90e)

**Caller-visible behavior** `org.languagetool.languagemodel.LuceneLanguageModel#getCount`. Look up a unigram and an adjacent token pair in the original language index.

**Result** Open. The old observer produced {"return": "55"}. On the upgrade it stopped before the selected method. The JVM traced the escaping java.lang.NoClassDefFoundError to `org.languagetool.languagemodel.LuceneSingleIndexLanguageModel$LuceneSearcher#<init>(Ljava/io/File;)V` at line 242. The recorded cause ends in `java.lang.ClassNotFoundException`. Both JVMs lacked `org.apache.lucene.codecs.PointsFormat`. The upgraded JAR introduced a symbolic reference to it. [Receipt](../../verification/external-upgrades/corpus-runs/v2-final-finite/02/compsuite-i-10.json)

**Scope** The upstream LuceneSingleIndexLanguageModelTest.testLanguageModel gives the counts for the unigram, bigram, trigram and missing token. All three index directories come byte-for-byte from both original commits. The check uses the original runtime dependencies. V0 was open and V1 was open. Original CI recorded `passed` before and `error` after. [Original CI](../../verification/external-upgrades/corpus-runs/restored-legacy-maven/compsuite-i-10/original-test/compsuite-i-10/new/summary.json)

**Review action** Review the dependency providing `org.apache.lucene.codecs.PointsFormat` and rerun the caller with compatible versions.

## ddd-leaven-v2 · compsuite-i-85

**Upgrade** org.hibernate:hibernate-entitymanager `4.2.0.Final` → `6.0.0.Alpha4`. [Original revisions](https://github.com/compsuite-team/ddd-leaven-v2/compare/a1a0cf597e430cf58afe627cd5a724fa33665d2e...f500f1ea3c84932963cdf847fea48a98f2f492d0)

**Caller-visible behavior** `pl.com.bottega.ecommerce.sales.application.impl.OrderingServiceImpl#confirm`. Confirm a previously calculated offer after changing the order quantity.

**Result** Open. parameter orderId has type pl.com.bottega.ecommerce.canonicalmodel.publishedlanguage.AggregateId, which is outside the objects a regression check makes: pl.com.bottega.ecommerce.canonicalmodel.publishedlanguage.AggregateId has 2 constructors; an object made by one of several is not supported yet [Receipt](../../verification/external-upgrades/corpus-runs/v2-final-native/04/current/compsuite-i-85.json)

**Scope** The native attempt used the registered original module and caller. The check uses the original runtime dependencies. V0 was open and V1 was open.

**Review action** Use the recorded original CI and address the first unresolved step.

## languagetool · compsuite-i-9

**Upgrade** org.apache.derby:derby `10.10.1.1` → `10.15.1.3`. [Original revisions](https://github.com/compsuite-team/languagetool/compare/fe77e85a2f7b472ba71564821e7545025eeda242...a63476d024688e9f28f02bd3d2a7660f6a4d75e2)

**Caller-visible behavior** `org.languagetool.dev.wikipedia.atom.MatchDatabase#add`. Store, list and update spelling matches using the database-backed caller.

**Result** Open. The upgraded JVM stopped before the selected method. Its escaping exception was `java.lang.RuntimeException`. The innermost recorded cause was `java.sql.SQLException` (No suitable driver found for jdbc:derby:atomFeedChecksDB;create=true). [Receipt](../../verification/external-upgrades/corpus-runs/v2-final-finite/07/compsuite-i-9.json)

**Scope** The original MatchDatabaseTest.test expects the inserted rule ID and diff 123, and an update to diff 124 on the matching rule. The original SQL predicate also requires the rule ID to match. Both POMs declare Derby in test scope. This environment does not supply a production-upgrade decision. The check uses Maven's original test classpath. V0 was open and V1 was open. Original CI recorded `passed` before and `error` after. [Original CI](../../verification/external-upgrades/corpus-runs/restored-legacy-maven/compsuite-i-9/original-test/compsuite-i-9/new/summary.json)

**Review action** Review this as a developer-test dependency. A production decision requires a production use.

## apollo · compsuite-i-4

**Upgrade** com.google.inject:guice `4.1.0` → `4.2.2`. [Original revisions](https://github.com/compsuite-team/apollo/compare/6b0a06a4682e8171cc17f5f61ccc8d87f6871b6d...b494d596132961f8f6dc7f229a1d0e4919da151b)

**Caller-visible behavior** `com.ctrip.framework.apollo.spi.DefaultConfigFactoryManager#getFactory`. Resolve the factory for an explicitly registered configuration namespace.

**Result** Open. The old observer produced {"return": "true"}. On the upgrade it stopped before the selected method. The JVM traced the escaping com.ctrip.framework.apollo.exceptions.ApolloConfigException to `com.ctrip.framework.apollo.build.ApolloInjector#getInstance(Ljava/lang/Class;)Ljava/lang/Object;` at line 38. The recorded cause ends in `java.lang.NoSuchMethodError`. [Receipt](../../verification/external-upgrades/corpus-runs/v2-final-finite/01/compsuite-i-4.json)

**Scope** Registration associates the supplied namespace with a specific factory. The factory manager publicly checks that registry first. Each test uses a fresh JVM and the real client injector. The check uses the original runtime dependencies. V0 was open and V1 was open.

**Review action** Resolve the earlier failure and rerun the downstream operation.

## fluent-validator · compsuite-i-62

**Upgrade** org.hibernate:hibernate-validator `5.2.1.Final` → `6.1.0.Final`. [Original revisions](https://github.com/compsuite-team/fluent-validator/compare/28119f2ae62ff9101e874a70a87baa639ecc681b...a7daf452b1db8a548d67b64d030d7d04f862b016)

**Caller-visible behavior** `com.baidu.unbiz.fluentvalidator.interceptor.FluentValidateInterceptor#invoke`. Invoke the validated service with an excluded group and observe its validation outcome.

**Result** Open. the tool's own checker met 1 gap, a construct it does not implement as the JVM does, and refused it (--gaps strict): jdk-constructor:java.util.LinkedHashSet.<init>()V@jdk-21.0.13 (java.util.LinkedHashSet.<init>() at org.slf4j.LoggerFactory.findPossibleStaticLoggerBinderPathSet:219). With --gaps assume it assumes instead that java.util.LinkedHashSet.<init>() constructs the object and does nothing else: it throws nothing and keeps nothing of its ar [Receipt](../../verification/external-upgrades/corpus-runs/v2-final-native/03/current/compsuite-i-62.json)

**Scope** The native attempt used the registered original module and caller. The check uses the original runtime dependencies. V0 was open and V1 was open.

**Review action** Use the recorded original CI and address the first unresolved step.

## citrus · compsuite-i-94

**Upgrade** org.springframework:spring-web `3.2.4.RELEASE` → `5.2.2.RELEASE`. [Original revisions](https://github.com/compsuite-team/citrus/compare/f728a4f1995343460ffb6df027775d61553d7c7e...0b844ff015dc31a24e3d85e1f66ee50fdc7f39f9)

**Caller-visible behavior** `com.alibaba.citrus.service.form.impl.validation.DateValidator#validate`. Validate dates on either side of the configured minimum and read the field state.

**Result** Open. validate is an instance method, whose receiver is outside the objects a regression check makes: the receiver, an object of com.alibaba.citrus.service.form.impl.validation.DateValidator made by its constructor: com.alibaba.citrus.service.form.impl.validation.DateValidator extends com.alibaba.citrus.service.form.support.AbstractOptionalValidator; a class made by its constructor must extend Object directly [Receipt](../../verification/external-upgrades/corpus-runs/v2-final-native/05/current/compsuite-i-94.json)

**Scope** The native attempt used the registered original module and caller. The check uses the original runtime dependencies. V0 was open and V1 was open.

**Review action** Use the recorded original CI and address the first unresolved step.

## togglz · compsuite-i-81

**Upgrade** org.apache.deltaspike.core:deltaspike-core-api `1.7.2` → `1.9.2`. [Original revisions](https://github.com/compsuite-team/togglz/compare/3418531ea79f1c858f008d5ec4fa83d0251601db...f74b56a98f000d3ab3913e90f3f47b2746809356)

**Caller-visible behavior** `org.togglz.deltaspike.activation.DeltaSpikePropertyActivationStrategy#getPropertyValue`. Read a configured feature flag and observe whether the caller activates the feature.

**Result** Changed. 2 of 2 inputs changed. Input 0 produced {"return": "true"} before and {"throws": "java.lang.RuntimeException"} after. [Receipt](../../verification/external-upgrades/corpus-runs/v2-final-finite/01/compsuite-i-81.json)

**Scope** Use the exact upstream test provider and service registration. Set the provider to each boolean and initialize the feature state to its opposite as in the developer test. The host supplies the original declared API. V0 was open and V1 was open. Original CI recorded `passed` before and `error` after. [Original CI](../../verification/external-upgrades/corpus-runs/v2-final-focused-ci/compsuite-i-81/new/summary.json)

**Review action** Review the changed return or exception before adopting the new pin.

## ea-async · compsuite-i-39

**Upgrade** org.ow2.asm:asm `6.2.1` → `7.2`. [Original revisions](https://github.com/compsuite-team/ea-async/compare/3a60b3ceb9ddd8647aa5ea5f6c72c7c99d85eefb...af90a83ddee0489e2fb4f3f8bf7b300d578fa1fc)

**Caller-visible behavior** `com.ea.async.instrumentation.Transformer#transform`. Transform and execute an asynchronous method and read its eventual result.

**Result** Preserved. Both versions matched the independent expectations on all 2 inputs. [Receipt](../../verification/external-upgrades/corpus-runs/v2-final-finite/02/compsuite-i-39.json)

**Scope** The input bytecode awaits and returns its completed Task argument. Its class bytes are fixed on the original ASM version. The upstream test expects hello; the second input verifies that the returned value follows its own argument. The check uses the original runtime dependencies. V0 was open and V1 was preserved.

**Review action** Keep the historical change open on this input domain.

## jvm-profiler · compsuite-i-29

**Upgrade** com.fasterxml.jackson.core:jackson-databind `2.9.10.1` → `2.10.1`. [Original revisions](https://github.com/compsuite-team/jvm-profiler/compare/03a21825f87a95b1d1291c035b9f885066dca9d0...279ece31518ff797eb149c57df01093cdd376daf)

**Caller-visible behavior** `com.uber.profiling.Arguments#runConfigProvider`. Apply a configuration provider and read the resulting interval and tag.

**Result** Changed. 1 of 2 inputs changed. Input 0 produced {"return": "tag1/9001/false"} before and {"return": "tag1/9000/true"} after. [Receipt](../../verification/external-upgrades/corpus-runs/v2-final-finite/02/compsuite-i-29.json)

**Scope** The declared provider supplies input settings only. An exact tag1 has an explicit override, while a different tag uses root values. Both expectations follow the original configuration contract and historical test. The check uses the original runtime dependencies. V0 was open and V1 was changed.

**Review action** Review the changed return or exception before adopting the new pin.

## Jupiter · compsuite-i-36

**Upgrade** org.ow2.asm:asm `6.0` → `7.2`. [Original revisions](https://github.com/compsuite-team/Jupiter/compare/2b16d7aba2137a57c0d84665cfda2a2b82df6be9...9c5a614e5875c5cf03434510c25b9f2b3505342a)

**Caller-visible behavior** `org.jupiter.common.util.Reflects#fastInvoke`. Choose and invoke an overloaded service method on the supplied arguments.

**Result** Changed. 2 of 2 inputs changed. Input 0 produced {"return": "Integer/CharSequence"} before and {"throws": "java.lang.IllegalArgumentException"} after. [Receipt](../../verification/external-upgrades/corpus-runs/v2-final-finite/02/compsuite-i-36.json)

**Scope** The service signatures and boxed-integer/StringBuilder setup mirror the original developer test. The expected overload accepts the exact boxed argument and the most specific compatible reference type. The check uses the original runtime dependencies. V0 was open and V1 was changed.

**Review action** Review the changed return or exception before adopting the new pin.

## nacos-spring-project · compsuite-i-103

**Upgrade** org.springframework:spring-core `3.2.18.RELEASE` → `5.2.2.RELEASE`. [Original revisions](https://github.com/compsuite-team/nacos-spring-project/compare/5e1d24dc64bb058ea0984a137de7ecb23c27a27a...67693f18a9427f1d46b6769fd4da3282207a37c7)

**Caller-visible behavior** `com.alibaba.nacos.spring.core.env.NacosPropertySourcePostProcessor#postProcessBeanFactory`. Register a property source and inspect its precedence and returned property.

**Result** Open. The upgraded JVM stopped before the selected method. Its escaping exception was `java.lang.NoClassDefFoundError`. The innermost recorded cause was `java.lang.ClassNotFoundException` (org.springframework.core.ErrorCoded). Fresh JVM lookups found `org.springframework.core.ErrorCoded` in the old upgraded JAR and absent from every new input JAR. [Receipt](../../verification/external-upgrades/corpus-runs/v2-final-finite/02/compsuite-i-103.json)

**Scope** The original developer test requires the source named first to head the environment and override user.name. The original Nacos HTTP handler supplies the input property on loopback. Two distinct returned values test precedence as well as source registration. The check uses the original runtime dependencies. V0 was open and V1 was open.

**Review action** Review the dependency providing `org.springframework.core.ErrorCoded` and rerun the caller with compatible versions.

## QRGen · compsuite-i-37

**Upgrade** com.google.zxing:core `3.3.0` → `3.4.0`. [Original revisions](https://github.com/compsuite-team/QRGen/compare/5d75d78080f7209e4ea15d3a08def04198741c7a...da2fc8cfba0e8ec28967256689a799b14babb04b)

**Caller-visible behavior** `net.glxn.qrgen.javase.QRCode#file`. Produce a QR image file from ordinary text with the default Java SE encoder.

**Result** Preserved. Both versions matched the independent expectations on all 3 inputs. [Receipt](../../verification/external-upgrades/corpus-runs/v2-final-finite/02/compsuite-i-37.json)

**Scope** The submitted text is its own independent round-trip expectation. Each image is read through Java ImageIO and decoded with its corresponding ZXing runtime. The historical test only asserted that the returned file was non-null. The check uses the original runtime dependencies. V0 was open and V1 was preserved.

**Review action** Keep the historical change open on this input domain.

## zt-exec · compsuite-i-80

**Upgrade** org.slf4j:slf4j-api `1.7.2` → `2.0.0-alpha1`. [Original revisions](https://github.com/compsuite-team/zt-exec/compare/5d23d18cba42cb03f95b89c2c459b01163408ebf...938bbeb343eb5fd465517c713fe9065ce997058a)

**Caller-visible behavior** `org.zeroturnaround.exec.stream.slf4j.Slf4jStream#of`. Construct a stream with a short logger name and observe its fully qualified name.

**Result** Changed. 2 of 2 inputs changed. Input 0 produced {"return": "UpgradeProbe.MyLogger"} before and {"return": "NOP"} after. [Receipt](../../verification/external-upgrades/corpus-runs/v2-final-finite/03/compsuite-i-80.json)

**Scope** The registered developer test requires the calling class name as the prefix for short logger names. A name containing package separators already specifies the logger. Both original POMs select logback-classic 1.1.2 for the registered test, including its logback-core dependency. That backend is fixed across the two runs. With the production API alone the old and new versions both used NOP. The check uses the original runtime dependencies. V0 was open and V1 was changed.

**Review action** Review the changed return or exception before adopting the new pin.

## ea-async · ea-async-27

**Upgrade** org.ow2.asm:asm `6.2` → `6.2.1`. [Original revisions](https://github.com/electronicarts/ea-async/compare/bbb45620d0b1d6623dd7c56938ad9d39f60451bc...a99e044708fac3654f621649d89bf1820bcd44a0)

**Caller-visible behavior** `com.ea.async.instrumentation.Transformer#transform`. Transform an async method holding an uninitialized value across await and read completion and result.

**Result** Preserved. Both versions matched the independent expectations on all 8 inputs. [Receipt](../../verification/external-upgrades/corpus-runs/v2-final-finite/03/ea-async-27.json)

**Scope** Each class has zero through three extra uninitialized stack copies across await. The already resolved input completes synchronously. The pending input completes after the argument is supplied. The generated function constructs the integer represented by that argument. The same original class bytes are passed on both releases. The check uses the original runtime dependencies. V0 was open and V1 was preserved.

**Review action** Retain this specific caller expectation when reviewing the upgrade.

## whatjdk · whatjdk-12

**Upgrade** org.ow2.asm:asm `6.2` → `6.2.1`. [Original revisions](https://github.com/nthalk/whatjdk/compare/206adaf9371d37dd308122f5f17e0f7cdaf3568c...e5574c3c06f9db307b96baa5937f9c19039df605)

**Caller-visible behavior** `com.iodesystems.whatjdk.ClassEntryExtractor#next`. Read an ordinary Java class and observe its class entry and referenced types.

**Result** Preserved. Both versions matched the independent expectations on all 4 inputs. [Receipt](../../verification/external-upgrades/corpus-runs/v2-final-finite/03/whatjdk-12.json)

**Scope** The input bytes and classfile declarations were fixed independently of application execution. Each class is packaged as the only member of a ZIP and consumed through the original archive iterator. The check uses the original runtime dependencies. V0 was open and V1 was preserved.

**Review action** Retain this specific caller expectation when reviewing the upgrade.

## incremental-analysis · incremental-analysis-28

**Upgrade** org.ow2.asm:asm `7.0` → `7.1`. [Original revisions](https://github.com/worksapplications/incremental-analysis/compare/f4633c66214da5bca3761136e88c71ec3b1eead0...4e33671a32cbad26d39404389165d07c35770070)

**Caller-visible behavior** `com.worksap.tools.spotbugs.maven.incremental.ClassSearcher#search`. Inspect the original class selection and the referenced class names in a small build.

**Result** Preserved. Both versions matched the independent expectations on all 5 inputs. [Receipt](../../verification/external-upgrades/corpus-runs/v2-final-finite/03/incremental-analysis-28.json)

**Scope** Two independently inspected classfiles carry SourceFile values Empty.java and Numbers.java. A matching changed source selects its class, and an unrelated source selects none. The two earlier input files have no SourceFile attribute and supply explicit negative controls. The check uses the original runtime dependencies. V0 was open and V1 was preserved.

**Review action** Retain this specific caller expectation when reviewing the upgrade.

## commons-text · commons-text-775

**Upgrade** org.apache.commons:commons-lang3 `3.20.0` → `3.21.0`. [Original revisions](https://github.com/apache/commons-text/compare/2b02f079f088a41e5bda78274872b3af3863a560...267f1d14a96824e60451bcb3e8e1fb8a7e882a10)

**Caller-visible behavior** `org.apache.commons.text.WordUtils#capitalizeFully`. Capitalize words with two delimiters and preserve their separators.

**Result** Preserved. Both versions matched the independent expectations on all 5 inputs. [Receipt](../../verification/external-upgrades/corpus-runs/v2-final-finite/03/commons-text-775.json)

**Scope** Within these explicitly listed inputs, lower-case each word and uppercase its initial. Empty strings and null pass through. UTC and English locale are fixed. The check uses the original runtime dependencies. V0 was open and V1 was preserved.

**Review action** Retain this specific caller expectation when reviewing the upgrade.

## commons-compress · commons-compress-767

**Upgrade** org.tukaani:xz `1.11` → `1.12`. [Original revisions](https://github.com/apache/commons-compress/compare/f3dfc34f01616abaf75cb255d59769d660428b83...b0757903222468a7a6b5e80a305ca749585129d5)

**Caller-visible behavior** `org.apache.commons.compress.compressors.xz.XZCompressorInputStream#read`. Decode an XZ stream and observe the exact decompressed bytes.

**Result** Preserved. Both versions matched the independent expectations on all 4 inputs. [Receipt](../../verification/external-upgrades/corpus-runs/v2-final-finite/04/commons-compress-767.json)

**Scope** The expected payloads are the independent bytes used to build the finite input frames. XZ uses Python liblzma. LZ4 uses literal blocks with an independent libxxhash header and content checksum. The check uses the original runtime dependencies. V0 was open and V1 was preserved.

**Review action** Retain this specific caller expectation when reviewing the upgrade.

## commons-compress · commons-compress-822

**Upgrade** commons-codec:commons-codec `1.22.1` → `1.23.0`. [Original revisions](https://github.com/apache/commons-compress/compare/8a79b1fd5fd993e94f3487f8acd2cd3ee9d4f15d...2cdf39ce4b191ac6c25a2e69905f82942872e587)

**Caller-visible behavior** `org.apache.commons.compress.compressors.lz4.FramedLZ4CompressorInputStream#read`. Decode a framed LZ4 stream including its checksum and read the exact payload.

**Result** Preserved. Both versions matched the independent expectations on all 4 inputs. [Receipt](../../verification/external-upgrades/corpus-runs/v2-final-finite/04/commons-compress-822.json)

**Scope** The expected payloads are the independent bytes used to build the finite input frames. XZ uses Python liblzma. LZ4 uses literal blocks with an independent libxxhash header and content checksum. The check uses the original runtime dependencies. V0 was open and V1 was preserved.

**Review action** Retain this specific caller expectation when reviewing the upgrade.

## commons-configuration · commons-configuration-565

**Upgrade** com.fasterxml.jackson.core:jackson-databind `2.18.3` → `2.19.0`. [Original revisions](https://github.com/apache/commons-configuration/compare/b485cdac96378f862237a6ad2fe3c8f57ae0612c...d2101a20e2b74ced47ae57dd3b6d1d90b03d409b)

**Caller-visible behavior** `org.apache.commons.configuration2.JSONConfiguration#read`. Read a JSON configuration and observe nested scalar and list values.

**Result** Preserved. Both versions matched the independent expectations on all 4 inputs. [Receipt](../../verification/external-upgrades/corpus-runs/v2-final-finite/04/commons-configuration-565.json)

**Scope** The literals specify their scalar or ordered sequence. For an absent key AbstractConfiguration.getList(Class, String) delegates to the overload with a null default. List elements in this finite domain contain no comma or bracket. The initial observer dereferenced that missing list; this observer retains null. The check uses the original runtime dependencies. V0 was open and V1 was preserved.

**Review action** Retain this specific caller expectation when reviewing the upgrade.

## commons-configuration · commons-configuration-601

**Upgrade** org.yaml:snakeyaml `2.4` → `2.5`. [Original revisions](https://github.com/apache/commons-configuration/compare/4c3ff511d02fb23b0ce967930bb828e8e69ee25e...0721015a499d1848bdf5a524c0f8a4f3a4fbbca2)

**Caller-visible behavior** `org.apache.commons.configuration2.YAMLConfiguration#read`. Read a YAML configuration and observe scalar and sequence values.

**Result** Preserved. Both versions matched the independent expectations on all 4 inputs. [Receipt](../../verification/external-upgrades/corpus-runs/v2-final-finite/04/commons-configuration-601.json)

**Scope** The literals specify their scalar or ordered sequence. For an absent key AbstractConfiguration.getList(Class, String) delegates to the overload with a null default. List elements in this finite domain contain no comma or bracket. The initial observer dereferenced that missing list; this observer retains null. The check uses the original runtime dependencies. V0 was open and V1 was preserved.

**Review action** Retain this specific caller expectation when reviewing the upgrade.

## cucumber-reporting · cucumber-reporting-1220

**Upgrade** commons-io:commons-io `2.17.0` → `2.18.0`. [Original revisions](https://github.com/damianszczepanik/cucumber-reporting/compare/d7c01732f611b6c9180c247d61e85bf5bbb38104...82d4caa2a3b42f6479af62efc3b27fee4e3b16ca)

**Caller-visible behavior** `net.masterthought.cucumber.ReportBuilder#generateReports`. Generate report files from a small valid report and inspect the output resources.

**Result** Preserved. Both versions matched the independent expectations on all 1 inputs. [Receipt](../../verification/external-upgrades/corpus-runs/v2-final-finite/04/cucumber-reporting-1220.json)

**Scope** The upstream input contains one feature with one passed step. The report API exposes those counts and writes its overview-features.html page under the default report directory. The check uses the original runtime dependencies. V0 was open and V1 was preserved.

**Review action** Retain this specific caller expectation when reviewing the upgrade.

## cucumber-reporting · cucumber-reporting-1198

**Upgrade** org.apache.commons:commons-lang3 `3.14.0` → `3.15.0`. [Original revisions](https://github.com/damianszczepanik/cucumber-reporting/compare/b0ec5fc9ea2dbd5ab980f69234a0dd66fa93504d...bf97b9ef1d60f9959a61379c3b3a682350e8e583)

**Caller-visible behavior** `net.masterthought.cucumber.util.StepNameFormatter#format`. Render argument spans in a step name and preserve surrounding characters.

**Result** Preserved. Both versions matched the independent expectations on all 4 inputs. [Receipt](../../verification/external-upgrades/corpus-runs/v2-final-finite/05/cucumber-reporting-1198.json)

**Scope** Escape HTML characters in the original step text, then mark the specified nonempty argument span at its zero-based offset. Empty and absent argument lists contribute no marks. The check uses the original runtime dependencies. V0 was open and V1 was preserved.

**Review action** Retain this specific caller expectation when reviewing the upgrade.

## commons-beanutils · commons-beanutils-440

**Upgrade** org.apache.commons:commons-lang3 `3.20.0` → `3.21.0`. [Original revisions](https://github.com/apache/commons-beanutils/compare/389264ff96c9e361ecb830a9813eae3f86f38d3a...5dc228566038283964a4f665c147282d462babdd)

**Caller-visible behavior** `org.apache.commons.beanutils2.MethodUtils#getMatchingAccessibleMethod`. Resolve an overloaded public method and observe the selected declaration.

**Result** Preserved. Both versions matched the independent expectations on all 5 inputs. [Receipt](../../verification/external-upgrades/corpus-runs/v2-final-finite/05/commons-beanutils-440.json)

**Scope** An exact public overload wins. Short is assignable only to Number. Boolean matches none of the three reference parameters. The check uses the original runtime dependencies. V0 was open and V1 was preserved.

**Review action** Retain this specific caller expectation when reviewing the upgrade.

## commons-csv · commons-csv-8993be87

**Upgrade** commons-io:commons-io `2.18.0` → `2.19.0`. [Original revisions](https://github.com/apache/commons-csv/compare/f7d8d7e7bd9780423a0088a9b18b755ec714c5ab...8993be875a32fdc336780b1610a2e002d320571e)

**Caller-visible behavior** `org.apache.commons.csv.CSVParser#nextRecord`. Read CSV records containing quoted separators and embedded line endings.

**Result** Preserved. Both versions matched the independent expectations on all 4 inputs. [Receipt](../../verification/external-upgrades/corpus-runs/v2-final-finite/05/commons-csv-8993be87.json)

**Scope** The four CSV literals cover a quoted separator, doubled quotes, embedded LF, empty fields and multiple records. An independent CSV reader supplies the expected field sequences. Length prefixes preserve the field boundaries. The check uses the original runtime dependencies. V0 was open and V1 was preserved.

**Review action** Retain this specific caller expectation when reviewing the upgrade.

## reflector · reflector-35

**Upgrade** org.ow2.asm:asm `5.0.3` → `7.1`. [Original revisions](https://github.com/jarviscraft/reflector/compare/a7421542ac2b34670c7c261539fc253d77526afc...b8a65d35911580a469964aa722f4cd989c1a5382)

**Caller-visible behavior** `ru.progrm_jarvis.reflector.bytecode.asm.AsmClassGenerator#newClassInstanceManipulator`. Generate the original reflection adapter and inspect the resulting callable class.

**Result** Open. Both revisions stopped before the selected method on 2 inputs. The innermost recorded cause was `java.lang.NullPointerException` (value is marked @NonNull but is null). [Receipt](../../verification/external-upgrades/corpus-runs/v2-final-finite/05/reflector-35.json)

**Scope** Both selected classes have accessible argument-free constructors. A working public generator should produce a fresh instance with each requested class identity. An original runtime that cannot create the adapter remains open. The check uses the original runtime dependencies. V0 was open and V1 was open.

**Review action** Use the recorded original CI and address the first unresolved step.

## commons-fileupload · commons-fileupload-377

**Upgrade** commons-io:commons-io `2.17.0` → `2.18.0`. [Original revisions](https://github.com/apache/commons-fileupload/compare/b958432b728f99c2f1142a896c8634fd1fc5b38c...9f9216c02d2176a678a8a51d68d6c8c03dbdbfcf)

**Caller-visible behavior** `org.apache.commons.fileupload2.core.MultipartInput#readBodyData`. Read a multipart body up to its boundary and observe the exact payload.

**Result** Preserved. Both versions matched the independent expectations on all 4 inputs. [Receipt](../../verification/external-upgrades/corpus-runs/v2-final-finite/05/commons-fileupload-377.json)

**Scope** The framing and headers are fixed and syntactically separate from the independently supplied payload. The expected count is the number of payload bytes and their encoding is lossless. The check uses the original runtime dependencies. V0 was open and V1 was preserved.

**Review action** Retain this specific caller expectation when reviewing the upgrade.

## commons-vfs · commons-vfs-55c96cfd

**Upgrade** commons-net:commons-net `3.12.0` → `3.13.0`. [Original revisions](https://github.com/apache/commons-vfs/compare/8ac9ec3cb4f7116e6809ef4d146736ac637939c7...55c96cfd2bdabe455058826ad86788f120b1425d)

**Caller-visible behavior** `org.apache.commons.vfs2.provider.ftp.FtpFileObject#doGetType`. Classify the remote entry from its parsed FTP file type.

**Result** Preserved. Both versions matched the independent expectations on all 3 inputs. [Receipt](../../verification/external-upgrades/corpus-runs/v2-final-finite/06/commons-vfs-55c96cfd.json)

**Scope** The server root contains one actual file and one actual directory. The Apache FTPServer and MINA versions come from the original project test environment and are held fixed on both sides. Each observation has its own temporary root and listener. The FTPServer parent POM specifies SLF4J API 1.7.36. It is supplied on both sides. The check uses the original runtime dependencies. V0 was open and V1 was preserved.

**Review action** Retain this specific caller expectation when reviewing the upgrade.

## commons-validator · commons-validator-86e32931

**Upgrade** commons-beanutils:commons-beanutils `1.9.4` → `1.10.0`. [Original revisions](https://github.com/apache/commons-validator/compare/a952e2fbe2b2226c72083f74cf66562a3118225f...86e32931594e3437cd8614311f5da7bc0c62613c)

**Caller-visible behavior** `org.apache.commons.validator.util.ValidatorUtils#getValueAsString`. Read a named property from a bean and observe the exact string or missing-value result.

**Result** Preserved. Both versions matched the independent expectations on all 4 inputs. [Receipt](../../verification/external-upgrades/corpus-runs/v2-final-finite/06/commons-validator-86e32931.json)

**Scope** Two public bean getters return the supplied string and integer 7. String conversion preserves the exact string or null and renders the integer in decimal. The check uses the original runtime dependencies. V0 was open and V1 was preserved.

**Review action** Retain this specific caller expectation when reviewing the upgrade.
