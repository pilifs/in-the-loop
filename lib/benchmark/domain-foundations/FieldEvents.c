/* JVMTI observation of field instructions on a historical JVM. No class is transformed. */
#include <jni.h>
#include <jvmti.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static jvmtiEnv *vm;
static FILE *events;
static atomic_int phase;

static void check(jvmtiError error) {
    if (error != JVMTI_ERROR_NONE) {
        fprintf(stderr, "field inventory JVMTI error %d\n", error);
        abort();
    }
}

static void release(char *value) {
    if (value) check((*vm)->Deallocate(vm, (unsigned char *)value));
}

static char *signature(jclass cls) {
    char *name = NULL;
    check((*vm)->GetClassSignature(vm, cls, &name, NULL));
    return name;
}

static int application(JNIEnv *jni, jclass cls, const char *name) {
    if (name[0] != 'L' || !strncmp(name, "Lfoundation/", 12)) return 0;
    jobject loader = NULL;
    check((*vm)->GetClassLoader(vm, cls, &loader));
    if (loader == NULL) return 0;
    (*jni)->DeleteLocalRef(jni, loader);
    return 1;
}

/* Take the JVM's status bits before advancing to the next part of the public call. */
static void JNICALL mark(JNIEnv *jni, jclass profile, jint next) {
    (void)profile;
    int old = atomic_exchange(&phase, 0);
    if (old) {
        jint count;
        jclass *classes;
        check((*vm)->GetLoadedClasses(vm, &count, &classes));
        for (int i = 0; i < count; i++) {
            char *name = signature(classes[i]);
            if (application(jni, classes[i], name)) {
                jint status;
                check((*vm)->GetClassStatus(vm, classes[i], &status));
                fprintf(events, "%d\tstatus\t%s\t%d\n", old, name, status);
            }
            release(name);
            (*jni)->DeleteLocalRef(jni, classes[i]);
        }
        check((*vm)->Deallocate(vm, (unsigned char *)classes));
        fflush(events);
    }
    atomic_store(&phase, next);
}

static void JNICALL prepared(jvmtiEnv *ti, JNIEnv *jni, jthread thread, jclass cls) {
    (void)ti; (void)thread;
    char *owner = signature(cls);
    if (!strcmp(owner, "Lfoundation/StartupProfile;")) {
        JNINativeMethod m = {"mark", "(I)V", (void *)mark};
        if ((*jni)->RegisterNatives(jni, cls, &m, 1) != JNI_OK) abort();
    }
    int buffer = !strcmp(owner, "Ljava/nio/Buffer;") || !strcmp(owner, "Ljava/nio/ByteBuffer;");
    if (application(jni, cls, owner) || buffer) {
        jint count;
        jfieldID *fields;
        check((*vm)->GetClassFields(vm, cls, &count, &fields));
        for (int i = 0; i < count; i++) {
            jint modifiers;
            check((*vm)->GetFieldModifiers(vm, cls, fields[i], &modifiers));
            int case_object = strstr(owner, "AvroDatumConverterFactory") != NULL ||
                !strcmp(owner, "Lorg/apache/hadoop/io/BytesWritable;");
            if ((modifiers & 8) || case_object || buffer) {
                check((*vm)->SetFieldAccessWatch(vm, cls, fields[i]));
                check((*vm)->SetFieldModificationWatch(vm, cls, fields[i]));
            }
        }
        check((*vm)->Deallocate(vm, (unsigned char *)fields));
    }
    release(owner);
}

static void field(JNIEnv *jni, jmethodID method, jlocation pc, jclass cls, jfieldID id,
                  jobject receiver, const char *op) {
    int active = atomic_load(&phase);
    if (!active) return;
    jclass caller;
    char *method_name, *descriptor, *name, *type;
    check((*vm)->GetMethodDeclaringClass(vm, method, &caller));
    check((*vm)->GetMethodName(vm, method, &method_name, &descriptor, NULL));
    check((*vm)->GetFieldName(vm, cls, id, &name, &type, NULL));
    char *writer = signature(caller), *owner = signature(cls);
    fprintf(events, "%d\t%s%s\t%s\t%s\t%s\t%lld\t%s\t%s\t%s\n", active, op,
            receiver == NULL ? "static" : "field", writer, method_name, descriptor, (long long)pc, owner, name, type);
    release(writer); release(owner); release(method_name); release(descriptor); release(name); release(type);
    (*jni)->DeleteLocalRef(jni, caller);
}

static void JNICALL read_field(jvmtiEnv *ti, JNIEnv *jni, jthread thread, jmethodID method, jlocation pc,
                               jclass cls, jobject object, jfieldID id) {
    (void)ti; (void)thread;
    field(jni, method, pc, cls, id, object, "get");
}

static void JNICALL write_field(jvmtiEnv *ti, JNIEnv *jni, jthread thread, jmethodID method, jlocation pc,
                                jclass cls, jobject object, jfieldID id, char kind, jvalue value) {
    (void)ti; (void)thread; (void)kind; (void)value;
    field(jni, method, pc, cls, id, object, "put");
}

JNIEXPORT jint JNICALL Agent_OnLoad(JavaVM *jvm, char *path, void *reserved) {
    (void)reserved;
    if (!path || !(events = fopen(path, "w")) ||
        (*jvm)->GetEnv(jvm, (void **)&vm, JVMTI_VERSION_1_2) != JNI_OK) return JNI_ERR;
    jvmtiCapabilities caps = {0};
    caps.can_generate_field_access_events = 1;
    caps.can_generate_field_modification_events = 1;
    check((*vm)->AddCapabilities(vm, &caps));
    jvmtiEventCallbacks callbacks = {0};
    callbacks.ClassPrepare = prepared;
    callbacks.FieldAccess = read_field;
    callbacks.FieldModification = write_field;
    check((*vm)->SetEventCallbacks(vm, &callbacks, sizeof(callbacks)));
    jvmtiEvent requested[] = {JVMTI_EVENT_CLASS_PREPARE, JVMTI_EVENT_FIELD_ACCESS, JVMTI_EVENT_FIELD_MODIFICATION};
    for (int i = 0; i < 3; i++)
        check((*vm)->SetEventNotificationMode(vm, JVMTI_ENABLE, requested[i], NULL));
    return JNI_OK;
}

JNIEXPORT void JNICALL Agent_OnUnload(JavaVM *jvm) {
    (void)jvm;
    if (events) fclose(events);
}
