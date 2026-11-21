# Dependency-upgrade reports for maintainers

Each report names the original consumer, the scope actually checked and the next review action. A finite decision covers the stated inputs and environment. Costs are measured by stage. Per-case model-token and dollar attribution is unavailable because all operator work used the same session.

## reflectasm · compsuite-i-38

**Upgrade** org.ow2.asm:asm `5.1` → `7.2`. [Original revision pair](https://github.com/compsuite-team/reflectasm/compare/7cab65bb46ccd17b07ad05dd6b83d92a695477fc...5c636af1a65b92fa570582628a27aa1e7d29f24b)

**Caller-visible behavior** `com.esotericsoftware.reflectasm.MethodAccess#get`. Construct an interface method accessor and invoke replace on a populated concurrent map.

**Result** Changed on 1 of 2 inputs. Input 0 produced {"return": "one/2"} before and {"throws": "java.lang.IllegalArgumentException"} after. [Evidence](../../verification/external-upgrades/corpus-runs/v1-finite/01/compsuite-i-38.json)

**Scope** The original developer test expects the previous map value and two entries. Object declares no exported accessor methods in this adapter. The complete-module reference records both outcomes. Each input ran twice per revision on fresh JVMs. Original module CI old failed before tests (0 tests), new failed before tests (0 tests). The original developer test recorded old failed before tests, no matching testcase, new failed before tests, no matching testcase. V0 took 0.1 s on this prepared workflow. The matched V1 native stage took 0.1 s. The finite caller stage took 4.8 s.

**Review action** Check whether the new caller behavior is acceptable before moving the pin. The recorded input supplies a regression test.

## retrofit · compsuite-i-1

**Upgrade** com.squareup.wire:wire-runtime `2.2.0` → `3.0.2`. [Original revision pair](https://github.com/compsuite-team/retrofit/compare/b8d593cf029652eb682434c0217ad92b5cbb005e...577716be23b960fe24b31b1edcdf6b01e88a692e)

**Caller-visible behavior** `retrofit2.converter.wire.WireResponseBodyConverter#convert`. Deserialize a serialized phone response and read the phone number.

**Result** Preserved the original expected observation on all 2 admitted inputs. The reported historical change was not reproduced on this observer. [Evidence](../../verification/external-upgrades/corpus-runs/v1-finite/01/compsuite-i-1.json)

**Scope** The checked-in generated Phone message has a length-delimited string in protobuf field 1. The first body is byte-for-byte the historical developer test. The short-string companion uses the same wire rule. Each input ran twice per revision on fresh JVMs. Original module CI old failed before tests (0 tests), new failed before tests (0 tests). The original developer test recorded old passed, new error (java.lang.NoSuchMethodError). V0 took 138.4 s on this prepared workflow. The matched V1 native stage took 0.1 s. The finite caller stage took 5.2 s.

**Review action** Keep the scoped result. The historical change still needs a reproducing input before it can inform this decision. Serialize a real Phone through the other half of the registered request/response test and read the outbound protobuf bytes. The old result was {"return": "Cg4oNTE5KSA4NjctNTMwOQ=="} and the new result was {"throws": "java.lang.NoSuchMethodError"}. [Additional original caller](../../verification/external-upgrades/corpus-runs/operational/01/compsuite-i-1.json)

## excel-streaming-reader · compsuite-i-70

**Upgrade** org.apache.poi:poi-ooxml `4.0.0` → `4.1.1`. [Original revision pair](https://github.com/compsuite-team/excel-streaming-reader/compare/3188aa5ed02b43aee8732c9027728d47f10a4e03...eed036e11b5aecaeb5889fae26505e9409bdc438)

**Caller-visible behavior** `com.monitorjbl.xlsx.impl.StreamingCell#getCellStyle`. Read the style of an unformatted cell from the original spreadsheet.

**Result** Open. New input 0: the original caller method was never entered. java.lang.IncompatibleClassChangeError: Found class org.apache.poi.util.POILogger, but interface was expected at org.apache.poi.openxml4j.opc.PackageRelationshipCollection.parseRelationshipsPart(PackageRelationshipCollection.java:303). [Evidence](../../verification/external-upgrades/corpus-runs/v1-finite/01/compsuite-i-70.json)

**Scope** The original pair and caller source were checked. The old runtime independently matched the expected result twice on 1 input(s). The paired claim remains open. Original module CI old passed (41 tests), new tests or lifecycle failed (41 tests). The original developer test recorded old passed, new error (java.lang.IncompatibleClassChangeError). V0 took 63.0 s on this prepared workflow. The matched V1 native stage took 0.7 s. The finite caller stage took 3.7 s.

**Review action** Use the existing CI evidence for this review. The named open step still needs a qualified caller result. Open the actual original spreadsheet with StreamingReader and read its worksheet count. The old result was {"return": "1"} and the new result was {"throws": "java.lang.IncompatibleClassChangeError"}. [Additional original caller](../../verification/external-upgrades/corpus-runs/operational/01/compsuite-i-70.json)

## languagetool · compsuite-i-10

**Upgrade** org.apache.lucene:lucene-backward-codecs `5.5.4` → `8.3.1`. [Original revision pair](https://github.com/compsuite-team/languagetool/compare/fe77e85a2f7b472ba71564821e7545025eeda242...d1263f08d7ad45e836e3169d0bdee01cbbebd90e)

**Caller-visible behavior** `org.languagetool.languagemodel.LuceneLanguageModel#getCount`. Look up a unigram and an adjacent token pair in the original language index.

**Result** Open. Old original Maven classpath: [ERROR] Failed to execute goal on project languagetool-core: Could not resolve dependencies for project org.languagetool:languagetool-core:jar:4.6: Failure to find biz.k11i:xgboost-predictor:jar:0.3.0 in https://repo.maven.apache.org/maven2 was cached in the local repos. [Evidence](../../verification/external-upgrades/corpus-runs/v1/01/current/compsuite-i-10.json)

**Scope** The original pair and caller source were checked. Native checking has yet to establish the specified caller observation. Original module CI old failed before tests (0 tests), new failed before tests (0 tests). The original developer test recorded old failed before tests, no matching testcase, new failed before tests, no matching testcase. V0 took 54.8 s on this prepared workflow. The matched V1 native stage took 12.9 s.

**Review action** Use the existing CI evidence for this review. The named open step still needs a qualified caller result.

## ddd-leaven-v2 · compsuite-i-85

**Upgrade** org.hibernate:hibernate-entitymanager `4.2.0.Final` → `6.0.0.Alpha4`. [Original revision pair](https://github.com/compsuite-team/ddd-leaven-v2/compare/a1a0cf597e430cf58afe627cd5a724fa33665d2e...f500f1ea3c84932963cdf847fea48a98f2f492d0)

**Caller-visible behavior** `pl.com.bottega.ecommerce.sales.application.impl.OrderingServiceImpl#confirm`. Confirm a previously calculated offer after changing the order quantity.

**Result** Open. Parameter orderId has type pl.com.bottega.ecommerce.canonicalmodel.publishedlanguage.AggregateId, which is outside the objects a regression check makes: pl.com.bottega.ecommerce.canonicalmodel.publishedlanguage.AggregateId has 2 constructors; an object made by one of several is not supported yet. [Evidence](../../verification/external-upgrades/corpus-runs/v1-complete/01/current/compsuite-i-85.json)

**Scope** The original pair and caller source were checked. Native checking has yet to establish the specified caller observation. Original module CI old passed (3 tests), new tests or lifecycle failed (3 tests). The original developer test recorded old passed, new error (java.lang.IllegalStateException). V0 took 57.3 s on this prepared workflow. The matched V1 native stage took 3.6 s. Native checking also ran on both complete original modules in 0.3 s.

**Review action** Use the existing CI evidence for this review. The named open step still needs a qualified caller result.

## languagetool · compsuite-i-9

**Upgrade** org.apache.derby:derby `10.10.1.1` → `10.15.1.3`. [Original revision pair](https://github.com/compsuite-team/languagetool/compare/fe77e85a2f7b472ba71564821e7545025eeda242...a63476d024688e9f28f02bd3d2a7660f6a4d75e2)

**Caller-visible behavior** `org.languagetool.dev.wikipedia.atom.MatchDatabase#add`. Store, list and update spelling matches using the database-backed caller.

**Result** Open. Old original Maven classpath: [ERROR] Failed to execute goal on project languagetool-wikipedia: Could not resolve dependencies for project org.languagetool:languagetool-wikipedia:jar:4.6: Failure to find biz.k11i:xgboost-predictor:jar:0.3.0 in https://repo.maven.apache.org/maven2 was cached in the l. [Evidence](../../verification/external-upgrades/corpus-runs/v1/01/current/compsuite-i-9.json)

**Scope** The original pair and caller source were checked. Native checking has yet to establish the specified caller observation. Original module CI old failed before tests (0 tests), new failed before tests (0 tests). The original developer test recorded old failed before tests, no matching testcase, new failed before tests, no matching testcase. V0 took 150.3 s on this prepared workflow. The matched V1 native stage took 4.8 s.

**Review action** Use the existing CI evidence for this review. The named open step still needs a qualified caller result.

## apollo · compsuite-i-4

**Upgrade** com.google.inject:guice `4.1.0` → `4.2.2`. [Original revision pair](https://github.com/compsuite-team/apollo/compare/6b0a06a4682e8171cc17f5f61ccc8d87f6871b6d...b494d596132961f8f6dc7f229a1d0e4919da151b)

**Caller-visible behavior** `com.ctrip.framework.apollo.spi.DefaultConfigFactoryManager#getFactory`. Resolve the factory for an explicitly registered configuration namespace.

**Result** Open. New input 0: the original caller method was never entered. com.ctrip.framework.apollo.exceptions.ApolloConfigException: Unable to load instance for type com.ctrip.framework.apollo.spi.ConfigRegistry! at com.ctrip.framework.apollo.build.ApolloInjector.getInstance(ApolloInjector.java:38) caused by com. [Evidence](../../verification/external-upgrades/corpus-runs/v1-finite/01/compsuite-i-4.json)

**Scope** The original pair and caller source were checked. The old runtime independently matched the expected result twice on 2 input(s). The paired claim remains open. Original module CI old failed before tests (0 tests), new tests or lifecycle failed (332 tests). The original developer test recorded old failed before tests, no matching testcase, new error (java.lang.ExceptionInInitializerError). V0 took 64.5 s on this prepared workflow. The matched V1 native stage took 0.2 s. The finite caller stage took 4.6 s. With restored upstream inputs, the named test recorded old passed, new error.

**Review action** Use the existing CI evidence for this review. The named open step still needs a qualified caller result.

## fluent-validator · compsuite-i-62

**Upgrade** org.hibernate:hibernate-validator `5.2.1.Final` → `6.1.0.Final`. [Original revision pair](https://github.com/compsuite-team/fluent-validator/compare/28119f2ae62ff9101e874a70a87baa639ecc681b...a7daf452b1db8a548d67b64d030d7d04f862b016)

**Caller-visible behavior** `com.baidu.unbiz.fluentvalidator.interceptor.FluentValidateInterceptor#invoke`. Invoke the validated service with an excluded group and observe its validation outcome.

**Result** Open. The tool's own checker met 1 gap, a construct it does not implement as the JVM does, and refused it (--gaps strict): jdk-constructor:java.util.LinkedHashSet.<init>()V@jdk-21.0.13 (java.util.LinkedHashSet.<init>() at org.slf4j.LoggerFactory.findPossibleStaticLoggerBinderPathSet:219). With --gaps assu. [Evidence](../../verification/external-upgrades/corpus-runs/v1-complete/01/current/compsuite-i-62.json)

**Scope** The original pair and caller source were checked. Native checking has yet to establish the specified caller observation. Original module CI old passed (94 tests), new tests or lifecycle failed (64 tests). The original developer test recorded old passed, new error (java.lang.IllegalStateException). V0 took 50.4 s on this prepared workflow. The matched V1 native stage took 1.8 s. Native checking also ran on both complete original modules in 0.4 s.

**Review action** Use the existing CI evidence for this review. The named open step still needs a qualified caller result.

## citrus · compsuite-i-94

**Upgrade** org.springframework:spring-web `3.2.4.RELEASE` → `5.2.2.RELEASE`. [Original revision pair](https://github.com/compsuite-team/citrus/compare/f728a4f1995343460ffb6df027775d61553d7c7e...0b844ff015dc31a24e3d85e1f66ee50fdc7f39f9)

**Caller-visible behavior** `com.alibaba.citrus.service.form.impl.validation.DateValidator#validate`. Validate dates on either side of the configured minimum and read the field state.

**Result** Open. Validate is an instance method, whose receiver is outside the objects a regression check makes: the receiver, an object of com.alibaba.citrus.service.form.impl.validation.DateValidator made by its constructor: com.alibaba.citrus.service.form.impl.validation.DateValidator extends com.alibaba.citrus.s. [Evidence](../../verification/external-upgrades/corpus-runs/v1-complete/01/current/compsuite-i-94.json)

**Scope** The original pair and caller source were checked. Native checking has yet to establish the specified caller observation. Original module CI old tests or lifecycle failed (1153 tests), new tests or lifecycle failed (1153 tests). The original developer test recorded old passed, new error (java.lang.NoSuchFieldError). V0 took 55.7 s on this prepared workflow. The matched V1 native stage took 2.4 s. Native checking also ran on both complete original modules in 0.2 s.

**Review action** Use the existing CI evidence for this review. The named open step still needs a qualified caller result.

## togglz · compsuite-i-81

**Upgrade** org.apache.deltaspike.core:deltaspike-core-api `1.7.2` → `1.9.2`. [Original revision pair](https://github.com/compsuite-team/togglz/compare/3418531ea79f1c858f008d5ec4fa83d0251601db...f74b56a98f000d3ab3913e90f3f47b2746809356)

**Caller-visible behavior** `org.togglz.deltaspike.activation.DeltaSpikePropertyActivationStrategy#getPropertyValue`. Read a configured feature flag and observe whether the caller activates the feature.

**Result** Open. Old Maven build could not load the original Bundlor packaging plugin. Its SpringSource ASM 3.1.0, SLF4J and Maven plugin API JARs were unavailable in the recorded release repositories. [Evidence](../../verification/external-upgrades/corpus-runs/v1-finite/01/compsuite-i-81.json)

**Scope** The original pair and caller source were checked. The finite attempt did not qualify both original executions. Original module CI old failed before tests (0 tests), new failed before tests (0 tests). The original developer test recorded old failed before tests, no matching testcase, new failed before tests, no matching testcase. V0 took 141.1 s on this prepared workflow. The matched V1 native stage took 6.0 s. The finite caller stage took 0.0 s. With restored upstream inputs, the named test recorded old failed before tests, new failed before tests.

**Review action** Use the existing CI evidence for this review. The named open step still needs a qualified caller result.

## ea-async · compsuite-i-39

**Upgrade** org.ow2.asm:asm `6.2.1` → `7.2`. [Original revision pair](https://github.com/compsuite-team/ea-async/compare/3a60b3ceb9ddd8647aa5ea5f6c72c7c99d85eefb...af90a83ddee0489e2fb4f3f8bf7b300d578fa1fc)

**Caller-visible behavior** `com.ea.async.instrumentation.Transformer#transform`. Transform and execute an asynchronous method and read its eventual result.

**Result** Preserved the original expected observation on all 2 admitted inputs. The reported historical change was not reproduced on this observer. [Evidence](../../verification/external-upgrades/corpus-runs/v1-finite/02/compsuite-i-39.json)

**Scope** The input bytecode awaits and returns its completed Task argument. Its class bytes are fixed on the original ASM version. The upstream test expects hello; the second input verifies that the returned value follows its own argument. Each input ran twice per revision on fresh JVMs. Original module CI old passed (106 tests), new tests or lifecycle failed (106 tests). The original developer test recorded old passed, new error (java.lang.IllegalArgumentException). V0 took 62.6 s on this prepared workflow. The matched V1 native stage took 0.1 s. The finite caller stage took 5.6 s.

**Review action** Keep the scoped result. The historical change still needs a reproducing input before it can inform this decision.

## jvm-profiler · compsuite-i-29

**Upgrade** com.fasterxml.jackson.core:jackson-databind `2.9.10.1` → `2.10.1`. [Original revision pair](https://github.com/compsuite-team/jvm-profiler/compare/03a21825f87a95b1d1291c035b9f885066dca9d0...279ece31518ff797eb149c57df01093cdd376daf)

**Caller-visible behavior** `com.uber.profiling.Arguments#runConfigProvider`. Apply a configuration provider and read the resulting interval and tag.

**Result** Changed on 1 of 2 inputs. Input 0 produced {"return": "tag1/9001/false"} before and {"return": "tag1/9000/true"} after. [Evidence](../../verification/external-upgrades/corpus-runs/v1-finite/02/compsuite-i-29.json)

**Scope** The declared provider supplies input settings only. An exact tag1 has an explicit override, while a different tag uses root values. Both expectations follow the original configuration contract and historical test. Each input ran twice per revision on fresh JVMs. Original module CI old passed (69 tests), new tests or lifecycle failed (64 tests). The original developer test recorded old passed, new failure (java.lang.AssertionError). V0 took 56.7 s on this prepared workflow. The matched V1 native stage took 0.3 s. The finite caller stage took 6.4 s.

**Review action** Check whether the new caller behavior is acceptable before moving the pin. The recorded input supplies a regression test.

## Jupiter · compsuite-i-36

**Upgrade** org.ow2.asm:asm `6.0` → `7.2`. [Original revision pair](https://github.com/compsuite-team/Jupiter/compare/2b16d7aba2137a57c0d84665cfda2a2b82df6be9...9c5a614e5875c5cf03434510c25b9f2b3505342a)

**Caller-visible behavior** `org.jupiter.common.util.Reflects#fastInvoke`. Choose and invoke an overloaded service method on the supplied arguments.

**Result** Changed on 2 of 2 inputs. Input 0 produced {"return": "Integer/CharSequence"} before and {"throws": "java.lang.IllegalArgumentException"} after. [Evidence](../../verification/external-upgrades/corpus-runs/v1-finite/02/compsuite-i-36.json)

**Scope** The service signatures and boxed-integer/StringBuilder setup mirror the original developer test. The expected overload accepts the exact boxed argument and the most specific compatible reference type. Each input ran twice per revision on fresh JVMs. Original module CI old passed (3 tests), new tests or lifecycle failed (3 tests). The original developer test recorded old passed, new error (java.lang.IllegalArgumentException). V0 took 60.3 s on this prepared workflow. The matched V1 native stage took 0.1 s. The finite caller stage took 5.0 s.

**Review action** Check whether the new caller behavior is acceptable before moving the pin. The recorded input supplies a regression test.

## nacos-spring-project · compsuite-i-103

**Upgrade** org.springframework:spring-core `3.2.18.RELEASE` → `5.2.2.RELEASE`. [Original revision pair](https://github.com/compsuite-team/nacos-spring-project/compare/5e1d24dc64bb058ea0984a137de7ecb23c27a27a...67693f18a9427f1d46b6769fd4da3282207a37c7)

**Caller-visible behavior** `com.alibaba.nacos.spring.core.env.NacosPropertySourcePostProcessor#postProcessBeanFactory`. Register a property source and inspect its precedence and returned property.

**Result** Open. New input 0: the original caller method was never entered. java.lang.NoClassDefFoundError: org/springframework/core/ErrorCoded at java.lang.ClassLoader.defineClass1(Native Method) caused by java.lang.ClassNotFoundException: org.springframework.core.ErrorCoded at java.net.URLClassLoader.findClass(URL. [Evidence](../../verification/external-upgrades/corpus-runs/v1-finite/02/compsuite-i-103.json)

**Scope** The original pair and caller source were checked. The old runtime independently matched the expected result twice on 2 input(s). The paired claim remains open. Original module CI old passed (48 tests), new tests or lifecycle failed (55 tests). The original developer test recorded old passed, new error (java.lang.NoClassDefFoundError). V0 took 131.6 s on this prepared workflow. The matched V1 native stage took 0.2 s. The finite caller stage took 6.1 s.

**Review action** Use the existing CI evidence for this review. The named open step still needs a qualified caller result.

## QRGen · compsuite-i-37

**Upgrade** com.google.zxing:core `3.3.0` → `3.4.0`. [Original revision pair](https://github.com/compsuite-team/QRGen/compare/5d75d78080f7209e4ea15d3a08def04198741c7a...da2fc8cfba0e8ec28967256689a799b14babb04b)

**Caller-visible behavior** `net.glxn.qrgen.javase.QRCode#file`. Produce a QR image file from ordinary text with the default Java SE encoder.

**Result** Preserved the original expected observation on all 3 admitted inputs. The reported historical change was not reproduced on this observer. [Evidence](../../verification/external-upgrades/corpus-runs/v1-finite/02/compsuite-i-37.json)

**Scope** The submitted text is its own independent round-trip expectation. Each image is read through Java ImageIO and decoded with its corresponding ZXing runtime. The historical test only asserted that the returned file was non-null. Each input ran twice per revision on fresh JVMs. Original module CI old passed (66 tests), new passed (66 tests). The original developer test recorded old passed, new passed. V0 took 61.8 s on this prepared workflow. The matched V1 native stage took 1.8 s. Native checking also ran on both complete original modules in 0.1 s. The finite caller stage took 8.9 s.

**Review action** Keep the scoped result. The historical change still needs a reproducing input before it can inform this decision.

## zt-exec · compsuite-i-80

**Upgrade** org.slf4j:slf4j-api `1.7.2` → `2.0.0-alpha1`. [Original revision pair](https://github.com/compsuite-team/zt-exec/compare/5d23d18cba42cb03f95b89c2c459b01163408ebf...938bbeb343eb5fd465517c713fe9065ce997058a)

**Caller-visible behavior** `org.zeroturnaround.exec.stream.slf4j.Slf4jStream#of`. Construct a stream with a short logger name and observe its fully qualified name.

**Result** Changed on 2 of 2 inputs. Input 0 produced {"return": "UpgradeProbe.MyLogger"} before and {"return": "NOP"} after. [Evidence](../../verification/external-upgrades/corpus-runs/v1-finite/03/compsuite-i-80.json)

**Scope** The registered developer test requires the calling class name as the prefix for short logger names. A name containing package separators already specifies the logger. Both original POMs select logback-classic 1.1.2 for the registered test, including its logback-core dependency. That backend is fixed across the two runs. With the production API alone the old and new versions both used NOP. Each input ran twice per revision on fresh JVMs. Original module CI old tests or lifecycle failed (90 tests), new tests or lifecycle failed (90 tests). The original developer test recorded old passed, new failure (org.junit.ComparisonFailure). V0 took 57.9 s on this prepared workflow. The matched V1 native stage took 0.2 s. The finite caller stage took 5.2 s.

**Review action** Check whether the new caller behavior is acceptable before moving the pin. The recorded input supplies a regression test.

## ea-async · ea-async-27

**Upgrade** org.ow2.asm:asm `6.2` → `6.2.1`. [Original revision pair](https://github.com/electronicarts/ea-async/compare/bbb45620d0b1d6623dd7c56938ad9d39f60451bc...a99e044708fac3654f621649d89bf1820bcd44a0)

**Caller-visible behavior** `com.ea.async.instrumentation.Transformer#transform`. Transform an async method holding an uninitialized value across await and read completion and result.

**Result** Preserved the original expected observation on all 8 admitted inputs. [Evidence](../../verification/external-upgrades/corpus-runs/v1-finite/03/ea-async-27.json)

**Scope** Each class has zero through three extra uninitialized stack copies across await. The already resolved input completes synchronously. The pending input completes after the argument is supplied. The generated function constructs the integer represented by that argument. The same original class bytes are passed on both releases. Each input ran twice per revision on fresh JVMs. Original module CI old passed (106 tests), new passed (106 tests). V0 took 0.1 s on this prepared workflow. The matched V1 native stage took 0.1 s. The finite caller stage took 20.4 s.

**Review action** Retain this caller expectation for the scoped dependency review. Use the ordinary test suite for the remaining application behavior.

## whatjdk · whatjdk-12

**Upgrade** org.ow2.asm:asm `6.2` → `6.2.1`. [Original revision pair](https://github.com/nthalk/whatjdk/compare/206adaf9371d37dd308122f5f17e0f7cdaf3568c...e5574c3c06f9db307b96baa5937f9c19039df605)

**Caller-visible behavior** `com.iodesystems.whatjdk.ClassEntryExtractor#next`. Read an ordinary Java class and observe its class entry and referenced types.

**Result** Preserved the original expected observation on all 4 admitted inputs. [Evidence](../../verification/external-upgrades/corpus-runs/v1-finite/03/whatjdk-12.json)

**Scope** The input bytes and classfile declarations were fixed independently of application execution. Each class is packaged as the only member of a ZIP and consumed through the original archive iterator. Each input ran twice per revision on fresh JVMs. Original module CI old zero tests (0 tests), new zero tests (0 tests). V0 took 145.0 s on this prepared workflow. The matched V1 native stage took 0.1 s. The finite caller stage took 9.6 s.

**Review action** Retain this caller expectation for the scoped dependency review. Use the ordinary test suite for the remaining application behavior.

## incremental-analysis · incremental-analysis-28

**Upgrade** org.ow2.asm:asm `7.0` → `7.1`. [Original revision pair](https://github.com/worksapplications/incremental-analysis/compare/f4633c66214da5bca3761136e88c71ec3b1eead0...4e33671a32cbad26d39404389165d07c35770070)

**Caller-visible behavior** `com.worksap.tools.spotbugs.maven.incremental.ClassSearcher#search`. Inspect the original class selection and the referenced class names in a small build.

**Result** Preserved the original expected observation on all 5 admitted inputs. [Evidence](../../verification/external-upgrades/corpus-runs/v1-finite/03/incremental-analysis-28.json)

**Scope** Two independently inspected classfiles carry SourceFile values Empty.java and Numbers.java. A matching changed source selects its class, and an unrelated source selects none. The two earlier input files have no SourceFile attribute and supply explicit negative controls. Each input ran twice per revision on fresh JVMs. Original module CI old tests or lifecycle failed (3 tests), new tests or lifecycle failed (3 tests). V0 took 62.7 s on this prepared workflow. The matched V1 native stage took 0.1 s. The finite caller stage took 11.6 s.

**Review action** Retain this caller expectation for the scoped dependency review. Use the ordinary test suite for the remaining application behavior.

## commons-text · commons-text-775

**Upgrade** org.apache.commons:commons-lang3 `3.20.0` → `3.21.0`. [Original revision pair](https://github.com/apache/commons-text/compare/2b02f079f088a41e5bda78274872b3af3863a560...267f1d14a96824e60451bcb3e8e1fb8a7e882a10)

**Caller-visible behavior** `org.apache.commons.text.WordUtils#capitalizeFully`. Capitalize words with two delimiters and preserve their separators.

**Result** Preserved the original expected observation on all 5 admitted inputs. [Evidence](../../verification/external-upgrades/corpus-runs/v1-finite/03/commons-text-775.json)

**Scope** Within these explicitly listed inputs, lower-case each word and uppercase its initial. Empty strings and null pass through. UTC and English locale are fixed. Each input ran twice per revision on fresh JVMs. Original module CI old tests or lifecycle failed (11 tests), new tests or lifecycle failed (11 tests). V0 took 55.6 s on this prepared workflow. The matched V1 native stage took 0.3 s. The finite caller stage took 10.9 s.

**Review action** Retain this caller expectation for the scoped dependency review. Use the ordinary test suite for the remaining application behavior.

## commons-compress · commons-compress-767

**Upgrade** org.tukaani:xz `1.11` → `1.12`. [Original revision pair](https://github.com/apache/commons-compress/compare/f3dfc34f01616abaf75cb255d59769d660428b83...b0757903222468a7a6b5e80a305ca749585129d5)

**Caller-visible behavior** `org.apache.commons.compress.compressors.xz.XZCompressorInputStream#read`. Decode an XZ stream and observe the exact decompressed bytes.

**Result** Preserved the original expected observation on all 4 admitted inputs. [Evidence](../../verification/external-upgrades/corpus-runs/v1-finite/04/commons-compress-767.json)

**Scope** The expected payloads are the independent bytes used to build the finite input frames. XZ uses Python liblzma. LZ4 uses literal blocks with an independent libxxhash header and content checksum. Each input ran twice per revision on fresh JVMs. Original module CI old tests or lifecycle failed (2904 tests), new tests or lifecycle failed (3107 tests). V0 took 149.6 s on this prepared workflow. The matched V1 native stage took 0.1 s. The finite caller stage took 10.8 s.

**Review action** Retain this caller expectation for the scoped dependency review. Use the ordinary test suite for the remaining application behavior.

## commons-compress · commons-compress-822

**Upgrade** commons-codec:commons-codec `1.22.1` → `1.23.0`. [Original revision pair](https://github.com/apache/commons-compress/compare/8a79b1fd5fd993e94f3487f8acd2cd3ee9d4f15d...2cdf39ce4b191ac6c25a2e69905f82942872e587)

**Caller-visible behavior** `org.apache.commons.compress.compressors.lz4.FramedLZ4CompressorInputStream#read`. Decode a framed LZ4 stream including its checksum and read the exact payload.

**Result** Preserved the original expected observation on all 4 admitted inputs. [Evidence](../../verification/external-upgrades/corpus-runs/v1-finite/04/commons-compress-822.json)

**Scope** The expected payloads are the independent bytes used to build the finite input frames. XZ uses Python liblzma. LZ4 uses literal blocks with an independent libxxhash header and content checksum. Each input ran twice per revision on fresh JVMs. Original module CI old tests or lifecycle failed (3456 tests), new tests or lifecycle failed (3300 tests). V0 took 62.6 s on this prepared workflow. The matched V1 native stage took 0.2 s. The finite caller stage took 10.1 s.

**Review action** Retain this caller expectation for the scoped dependency review. Use the ordinary test suite for the remaining application behavior.

## commons-configuration · commons-configuration-565

**Upgrade** com.fasterxml.jackson.core:jackson-databind `2.18.3` → `2.19.0`. [Original revision pair](https://github.com/apache/commons-configuration/compare/b485cdac96378f862237a6ad2fe3c8f57ae0612c...d2101a20e2b74ced47ae57dd3b6d1d90b03d409b)

**Caller-visible behavior** `org.apache.commons.configuration2.JSONConfiguration#read`. Read a JSON configuration and observe nested scalar and list values.

**Result** Preserved the original expected observation on all 4 admitted inputs. [Evidence](../../verification/external-upgrades/corpus-runs/v1-finite/04/commons-configuration-565.json)

**Scope** The literals specify their scalar or ordered sequence. For an absent key AbstractConfiguration.getList(Class, String) delegates to the overload with a null default. List elements in this finite domain contain no comma or bracket. The initial observer dereferenced that missing list; this observer retains null. Each input ran twice per revision on fresh JVMs. Original module CI old passed (3011 tests), new passed (3011 tests). V0 took 54.1 s on this prepared workflow. The matched V1 native stage took 0.4 s. The finite caller stage took 18.5 s.

**Review action** Retain this caller expectation for the scoped dependency review. Use the ordinary test suite for the remaining application behavior.

## commons-configuration · commons-configuration-601

**Upgrade** org.yaml:snakeyaml `2.4` → `2.5`. [Original revision pair](https://github.com/apache/commons-configuration/compare/4c3ff511d02fb23b0ce967930bb828e8e69ee25e...0721015a499d1848bdf5a524c0f8a4f3a4fbbca2)

**Caller-visible behavior** `org.apache.commons.configuration2.YAMLConfiguration#read`. Read a YAML configuration and observe scalar and sequence values.

**Result** Preserved the original expected observation on all 4 admitted inputs. [Evidence](../../verification/external-upgrades/corpus-runs/v1-finite/04/commons-configuration-601.json)

**Scope** The literals specify their scalar or ordered sequence. For an absent key AbstractConfiguration.getList(Class, String) delegates to the overload with a null default. List elements in this finite domain contain no comma or bracket. The initial observer dereferenced that missing list; this observer retains null. Each input ran twice per revision on fresh JVMs. Original module CI old passed (3012 tests), new passed (3012 tests). V0 took 60.1 s on this prepared workflow. The matched V1 native stage took 0.5 s. The finite caller stage took 16.9 s.

**Review action** Retain this caller expectation for the scoped dependency review. Use the ordinary test suite for the remaining application behavior.

## cucumber-reporting · cucumber-reporting-1220

**Upgrade** commons-io:commons-io `2.17.0` → `2.18.0`. [Original revision pair](https://github.com/damianszczepanik/cucumber-reporting/compare/d7c01732f611b6c9180c247d61e85bf5bbb38104...82d4caa2a3b42f6479af62efc3b27fee4e3b16ca)

**Caller-visible behavior** `net.masterthought.cucumber.ReportBuilder#generateReports`. Generate report files from a small valid report and inspect the output resources.

**Result** Preserved the original expected observation on all 1 admitted inputs. [Evidence](../../verification/external-upgrades/corpus-runs/v1-finite/04/cucumber-reporting-1220.json)

**Scope** The upstream input contains one feature with one passed step. The report API exposes those counts and writes its overview-features.html page under the default report directory. Each input ran twice per revision on fresh JVMs. Original module CI old passed (665 tests), new passed (665 tests). V0 took 136.4 s on this prepared workflow. The matched V1 native stage took 0.4 s. The finite caller stage took 6.1 s.

**Review action** Retain this caller expectation for the scoped dependency review. Use the ordinary test suite for the remaining application behavior.

## cucumber-reporting · cucumber-reporting-1198

**Upgrade** org.apache.commons:commons-lang3 `3.14.0` → `3.15.0`. [Original revision pair](https://github.com/damianszczepanik/cucumber-reporting/compare/b0ec5fc9ea2dbd5ab980f69234a0dd66fa93504d...bf97b9ef1d60f9959a61379c3b3a682350e8e583)

**Caller-visible behavior** `net.masterthought.cucumber.util.StepNameFormatter#format`. Render argument spans in a step name and preserve surrounding characters.

**Result** Preserved the original expected observation on all 4 admitted inputs. [Evidence](../../verification/external-upgrades/corpus-runs/v1-finite/05/cucumber-reporting-1198.json)

**Scope** Escape HTML characters in the original step text, then mark the specified nonempty argument span at its zero-based offset. Empty and absent argument lists contribute no marks. Each input ran twice per revision on fresh JVMs. Original module CI old passed (664 tests), new passed (664 tests). V0 took 61.6 s on this prepared workflow. The matched V1 native stage took 0.1 s. The finite caller stage took 14.5 s.

**Review action** Retain this caller expectation for the scoped dependency review. Use the ordinary test suite for the remaining application behavior.

## commons-beanutils · commons-beanutils-440

**Upgrade** org.apache.commons:commons-lang3 `3.20.0` → `3.21.0`. [Original revision pair](https://github.com/apache/commons-beanutils/compare/389264ff96c9e361ecb830a9813eae3f86f38d3a...5dc228566038283964a4f665c147282d462babdd)

**Caller-visible behavior** `org.apache.commons.beanutils2.MethodUtils#getMatchingAccessibleMethod`. Resolve an overloaded public method and observe the selected declaration.

**Result** Preserved the original expected observation on all 5 admitted inputs. [Evidence](../../verification/external-upgrades/corpus-runs/v1-finite/05/commons-beanutils-440.json)

**Scope** An exact public overload wins. Short is assignable only to Number. Boolean matches none of the three reference parameters. Each input ran twice per revision on fresh JVMs. Original module CI old passed (1315 tests), new passed (1315 tests). V0 took 58.7 s on this prepared workflow. The matched V1 native stage took 0.1 s. The finite caller stage took 12.6 s.

**Review action** Retain this caller expectation for the scoped dependency review. Use the ordinary test suite for the remaining application behavior.

## commons-csv · commons-csv-8993be87

**Upgrade** commons-io:commons-io `2.18.0` → `2.19.0`. [Original revision pair](https://github.com/apache/commons-csv/compare/f7d8d7e7bd9780423a0088a9b18b755ec714c5ab...8993be875a32fdc336780b1610a2e002d320571e)

**Caller-visible behavior** `org.apache.commons.csv.CSVParser#nextRecord`. Read CSV records containing quoted separators and embedded line endings.

**Result** Preserved the original expected observation on all 4 admitted inputs. [Evidence](../../verification/external-upgrades/corpus-runs/v1-finite/05/commons-csv-8993be87.json)

**Scope** The four CSV literals cover a quoted separator, doubled quotes, embedded LF, empty fields and multiple records. An independent CSV reader supplies the expected field sequences. Length prefixes preserve the field boundaries. Each input ran twice per revision on fresh JVMs. Original module CI old passed (914 tests), new passed (914 tests). V0 took 62.0 s on this prepared workflow. The matched V1 native stage took 0.1 s. The finite caller stage took 9.6 s.

**Review action** Retain this caller expectation for the scoped dependency review. Use the ordinary test suite for the remaining application behavior.

## reflector · reflector-35

**Upgrade** org.ow2.asm:asm `5.0.3` → `7.1`. [Original revision pair](https://github.com/jarviscraft/reflector/compare/a7421542ac2b34670c7c261539fc253d77526afc...b8a65d35911580a469964aa722f4cd989c1a5382)

**Caller-visible behavior** `ru.progrm_jarvis.reflector.bytecode.asm.AsmClassGenerator#newClassInstanceManipulator`. Generate the original reflection adapter and inspect the resulting callable class.

**Result** Open. Old input 0: the original caller method was never entered. java.lang.ExceptionInInitializerError: null at ru.progrm_jarvis.reflector.bytecode.asm.AsmClassGenerator.<init>(AsmClassGenerator.java:26) caused by java.lang.NullPointerException: value is marked @NonNull but is null at ru.progrm_jarvis.ref. [Evidence](../../verification/external-upgrades/corpus-runs/v1-finite/05/reflector-35.json)

**Scope** The original pair and caller source were checked. The finite attempt did not qualify both original executions. Original module CI old zero tests (0 tests), new zero tests (0 tests). V0 took 128.3 s on this prepared workflow. The matched V1 native stage took 11.3 s. Native checking also ran on both complete original modules in 0.2 s. The finite caller stage took 1.1 s.

**Review action** Use the existing CI evidence for this review. The named open step still needs a qualified caller result.

## commons-fileupload · commons-fileupload-377

**Upgrade** commons-io:commons-io `2.17.0` → `2.18.0`. [Original revision pair](https://github.com/apache/commons-fileupload/compare/b958432b728f99c2f1142a896c8634fd1fc5b38c...9f9216c02d2176a678a8a51d68d6c8c03dbdbfcf)

**Caller-visible behavior** `org.apache.commons.fileupload2.core.MultipartInput#readBodyData`. Read a multipart body up to its boundary and observe the exact payload.

**Result** Preserved the original expected observation on all 4 admitted inputs. [Evidence](../../verification/external-upgrades/corpus-runs/v1-finite/05/commons-fileupload-377.json)

**Scope** The framing and headers are fixed and syntactically separate from the independently supplied payload. The expected count is the number of payload bytes and their encoding is lossless. Each input ran twice per revision on fresh JVMs. Original module CI old passed (49 tests), new passed (49 tests). V0 took 64.8 s on this prepared workflow. The matched V1 native stage took 0.1 s. The finite caller stage took 9.2 s.

**Review action** Retain this caller expectation for the scoped dependency review. Use the ordinary test suite for the remaining application behavior.

## commons-vfs · commons-vfs-55c96cfd

**Upgrade** commons-net:commons-net `3.12.0` → `3.13.0`. [Original revision pair](https://github.com/apache/commons-vfs/compare/8ac9ec3cb4f7116e6809ef4d146736ac637939c7...55c96cfd2bdabe455058826ad86788f120b1425d)

**Caller-visible behavior** `org.apache.commons.vfs2.provider.ftp.FtpFileObject#doGetType`. Classify the remote entry from its parsed FTP file type.

**Result** Preserved the original expected observation on all 3 admitted inputs. [Evidence](../../verification/external-upgrades/corpus-runs/v1-finite/06/commons-vfs-55c96cfd.json)

**Scope** The server root contains one actual file and one actual directory. The Apache FTPServer and MINA versions come from the original project test environment and are held fixed on both sides. Each observation has its own temporary root and listener. The FTPServer parent POM specifies SLF4J API 1.7.36. It is supplied on both sides. Each input ran twice per revision on fresh JVMs. Original module CI old tests or lifecycle failed (3201 tests), new tests or lifecycle failed (3201 tests). V0 took 57.4 s on this prepared workflow. The matched V1 native stage took 0.2 s. The finite caller stage took 12.9 s.

**Review action** Retain this caller expectation for the scoped dependency review. Use the ordinary test suite for the remaining application behavior.

## commons-validator · commons-validator-86e32931

**Upgrade** commons-beanutils:commons-beanutils `1.9.4` → `1.10.0`. [Original revision pair](https://github.com/apache/commons-validator/compare/a952e2fbe2b2226c72083f74cf66562a3118225f...86e32931594e3437cd8614311f5da7bc0c62613c)

**Caller-visible behavior** `org.apache.commons.validator.util.ValidatorUtils#getValueAsString`. Read a named property from a bean and observe the exact string or missing-value result.

**Result** Preserved the original expected observation on all 4 admitted inputs. [Evidence](../../verification/external-upgrades/corpus-runs/v1-finite/06/commons-validator-86e32931.json)

**Scope** Two public bean getters return the supplied string and integer 7. String conversion preserves the exact string or null and renders the integer in decimal. Each input ran twice per revision on fresh JVMs. Original module CI old passed (990 tests), new passed (990 tests). V0 took 52.9 s on this prepared workflow. The matched V1 native stage took 0.1 s. The finite caller stage took 10.9 s.

**Review action** Retain this caller expectation for the scoped dependency review. Use the ordinary test suite for the remaining application behavior.

