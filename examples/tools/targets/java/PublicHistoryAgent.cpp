// Opt-in JVMTI coverage for an original local test launch and its child JVMs.
// The input lists method descriptors and test class bytes. Subject bytecode is never rewritten.
#include <jvmti.h>
#include <unistd.h>
#include <fstream>
#include <mutex>
#include <sstream>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace {
using std::string;
struct Member {
    string owner, name, signature, selector;
    jlong loader = 0;
    bool exported = false;
    bool is_static = false;
};
struct Call { jmethodID method; jlong object; jlong id; };
struct History { jlong test = 0; std::vector<Call> calls; };
struct Tap { string role; std::vector<int> reference_slots; };
jvmtiEnv* ti;
std::recursive_mutex lock;
std::ofstream out;
std::ofstream class_bytes;
std::unordered_set<string> changes, public_shapes, tests, prefixes;
std::unordered_set<string> tap_owners;
std::unordered_map<string,Tap> taps;
std::unordered_map<jmethodID, Member> methods;
std::unordered_map<jlong, History> histories;
long long next_tag = 0, next_call = 0, sequence = 0, limit = 0;
bool truncated = false;

void release(void* memory) {
    if (memory) ti->Deallocate(static_cast<unsigned char*>(memory));
}

jlong tag(jobject object) {
    if (!object) return 0;
    jlong value = 0;
    if (ti->GetTag(object, &value) != JVMTI_ERROR_NONE) return -1;
    if (!value) {
        value = ++next_tag;
        if (ti->SetTag(object, value) != JVMTI_ERROR_NONE) return -1;
    }
    return value;
}

string owner_of(jclass klass) {
    char* signature = nullptr;
    if (ti->GetClassSignature(klass, &signature, nullptr) != JVMTI_ERROR_NONE) return "";
    string name(signature);
    release(signature);
    return name.size() > 2 && name[0] == 'L' ? name.substr(1, name.size()-2) : name;
}

bool production(const string& owner) {
    for (const auto& prefix : prefixes) if (owner.compare(0,prefix.size(),prefix) == 0) return true;
    return false;
}

bool test_class(const string& owner) {
    return tests.count(owner) || tests.count(owner.substr(0, owner.find('$')));
}

string key(jlong loader, const string& owner) { return std::to_string(loader) + ":" + owner; }

const Member& member(jmethodID id) {
    auto saved = methods.find(id);
    if (saved != methods.end()) return saved->second;
    Member m;
    jclass klass;
    char *name = nullptr, *descriptor = nullptr;
    if (ti->GetMethodDeclaringClass(id,&klass) == JVMTI_ERROR_NONE &&
            ti->GetMethodName(id,&name,&descriptor,nullptr) == JVMTI_ERROR_NONE) {
        m.owner = owner_of(klass);
        m.name = name; m.signature = descriptor; m.selector = m.owner + "#" + name + descriptor;
        jint class_mod = 0, method_mod = 0;
        jobject loader = nullptr;
        ti->GetClassModifiers(klass,&class_mod);
        ti->GetMethodModifiers(id,&method_mod);
        ti->GetClassLoader(klass,&loader);
        m.loader = tag(loader);
        m.exported = (class_mod & 1) && (method_mod & 1) && !(method_mod & 0x1040);
        m.is_static = method_mod & 8;
    }
    release(name); release(descriptor);
    return methods.emplace(id,m).first->second;
}

jlong receiver(jthread thread, int depth, const Member& method) {
    if (method.is_static) return 0;
    jobject object = nullptr;
    if (ti->GetLocalInstance(thread,depth,&object) != JVMTI_ERROR_NONE) return -1;
    return tag(object);
}

void line(const string& event) {
    if (sequence >= limit) {
        if (!truncated) out << "LIMIT\t" << limit << std::endl;
        truncated = true;
        return;
    }
    out << ++sequence << '\t' << event << '\n';
}

void JNICALL loaded(jvmtiEnv*, JNIEnv*, jclass, jobject loader, const char* name, jobject,
                    jint length, const unsigned char* bytes, jint*, unsigned char**) {
    if (!name || (!production(name) && !test_class(name) && !tap_owners.count(name))) return;
    std::lock_guard<std::recursive_mutex> guard(lock);
    auto offset = class_bytes.tellp();
    class_bytes.write(reinterpret_cast<const char*>(bytes),length);
    out << "CLASS\t" << key(tag(loader),name) << '\t' << offset << '\t' << length << '\n';
}

void JNICALL prepared(jvmtiEnv*, JNIEnv*, jthread, jclass klass) {
    string owner = owner_of(klass);
    if (!production(owner) && !test_class(owner) && !tap_owners.count(owner)) return;
    std::lock_guard<std::recursive_mutex> guard(lock);
    jint count = 0;
    jmethodID* ids = nullptr;
    if (ti->GetClassMethods(klass,&count,&ids) != JVMTI_ERROR_NONE) return;
    for (int i=0; i<count; ++i) {
        const auto& m = member(ids[i]);
        bool test = test_class(owner) && !m.name.empty() && m.name[0] != '<' && m.name.find("lambda$") != 0;
        if (!test && !changes.count(m.selector) && !taps.count(m.selector) && !(m.exported && public_shapes.count(m.name+m.signature))) continue;
        jlocation start = -1, end = -1;
        if (ti->GetMethodLocation(ids[i],&start,&end) == JVMTI_ERROR_NONE && start >= 0)
            ti->SetBreakpoint(ids[i],start);
    }
    release(ids);
}

void JNICALL hit(jvmtiEnv*, JNIEnv*, jthread thread, jmethodID id, jlocation) {
    std::lock_guard<std::recursive_mutex> guard(lock);
    if (truncated) return;
    const Member m = member(id);
    jlong tid = tag(thread);
    auto& h = histories[tid];
    auto tap = taps.find(m.selector);
    if (tap != taps.end()) {
        jvmtiFrameInfo callers[2]; jint count = 0;
        if (ti->GetStackTrace(thread,0,2,callers,&count) != JVMTI_ERROR_NONE || count != 2) return;
        const Member caller = member(callers[1].method);
        std::ostringstream event;
        event << "tap\t" << tid << '\t' << h.test << '\t' << tap->second.role << '\t' << m.loader
              << '\t' << m.selector << '\t' << caller.selector << '\t' << callers[1].location
              << '\t' << receiver(thread,0,m);
        for (int slot : tap->second.reference_slots) {
            jobject value = nullptr;
            auto error = ti->GetLocalObject(thread,0,slot,&value);
            event << '\t' << (error == JVMTI_ERROR_NONE ? tag(value) : -1);
        }
        jvmtiFrameInfo trace[96]; jint depth = 0;
        event << "\tSTACK";
        if (ti->GetStackTrace(thread,0,96,trace,&depth) == JVMTI_ERROR_NONE) {
            for (int i=0; i<depth; ++i) {
                const Member f = member(trace[i].method);
                jlong object = production(f.owner) || tap_owners.count(f.owner) || test_class(f.owner) ? receiver(thread,i,f) : 0;
                event << '\t' << f.loader << ' ' << trace[i].location << ' ' << (f.exported?1:0) << ' ' << object << ' ' << f.selector;
            }
        }
        line(event.str());
    }
    if (test_class(m.owner)) {
        if (!h.test && ti->NotifyFramePop(thread,0) == JVMTI_ERROR_NONE) {
            h.test = ++next_call;
            h.calls.push_back({id,0,h.test});
            line("test\t" + std::to_string(tid) + "\t" + std::to_string(h.test) + "\t" + m.selector);
        }
        return;
    }
    bool changed = changes.count(m.selector);
    jvmtiFrameInfo stack[96];
    jint n = 0;
    if (ti->GetStackTrace(thread,0,changed ? 96 : 2,stack,&n) != JVMTI_ERROR_NONE || n < 2) return;
    const Member caller = member(stack[1].method);
    jlong object = receiver(thread,0,m);
    string common = std::to_string(tid) + "\t" + std::to_string(h.test) + "\t";
    if (m.exported && test_class(caller.owner)) {
        if (ti->NotifyFramePop(thread,0) == JVMTI_ERROR_NONE) {
            jlong call = ++next_call;
            h.calls.push_back({id,object,call});
            line("entry\t" + common + std::to_string(call) + "\t" + std::to_string(object) + "\t"
                 + std::to_string(m.loader) + "\t" + m.selector + "\t" + std::to_string(caller.loader) + "\t"
                 + caller.selector + "\t" + std::to_string(stack[1].location));
        }
    }
    if (!changed) return;
    std::ostringstream frames;
    for (int depth = 0; depth < n; ++depth) {
        const Member f = member(stack[depth].method);
        frames << '\t' << f.loader << ' ' << stack[depth].location << ' ' << (f.exported ? 1:0)
               << ' ' << (production(f.owner) ? receiver(thread,depth,f) : 0) << ' ' << f.selector;
    }
    line("hit\t" + common + std::to_string(object) + frames.str());
}

void JNICALL returned(jvmtiEnv*, JNIEnv*, jthread thread, jmethodID method, jboolean exception) {
    std::lock_guard<std::recursive_mutex> guard(lock);
    if (truncated) return;
    jlong tid = tag(thread);
    auto& h = histories[tid];
    if (h.calls.empty() || h.calls.back().method != method) return;
    auto call = h.calls.back(); h.calls.pop_back();
    line("exit\t" + std::to_string(tid) + "\t" + std::to_string(h.test) + "\t"
         + std::to_string(call.id) + "\t" + (exception ? "throw":"return"));
    if (call.id == h.test) h.test = 0;
}

void JNICALL ended(jvmtiEnv*, JNIEnv*) {
    std::lock_guard<std::recursive_mutex> guard(lock);
    out << "END\t" << sequence << '\t' << truncated << std::endl;
    class_bytes.flush();
}
}

JNIEXPORT jint JNICALL Agent_OnLoad(JavaVM* vm, char* options, void*) {
    std::ifstream config(options ? options : "");
    string entry, directory;
    while (std::getline(config,entry)) {
        auto tab = entry.find('\t');
        if (tab == string::npos) return JNI_ERR;
        string key = entry.substr(0,tab), value = entry.substr(tab+1);
        if (key == "changed") changes.insert(value);
        else if (key == "public") public_shapes.insert(value);
        else if (key == "test") tests.insert(value);
        else if (key == "prefix") prefixes.insert(value);
        else if (key == "tap") {
            std::istringstream row(value);
            Tap rule; string member; int slot;
            if (!(row >> rule.role >> member) || member.find('#') == string::npos) return JNI_ERR;
            while (row >> slot) {
                if (slot < 0 || slot > 255) return JNI_ERR;
                rule.reference_slots.push_back(slot);
            }
            taps.emplace(member,rule);
            tap_owners.insert(member.substr(0,member.find('#')));
        }
        else if (key == "directory") directory = value;
        else if (key == "limit") {
            std::istringstream number(value);
            if (!(number >> limit)) return JNI_ERR;
        }
        else return JNI_ERR;
    }
    if (directory.empty() || changes.empty() || prefixes.empty() || tests.empty() || limit < 1 || limit > 262144) return JNI_ERR;
    out.open(directory + "/" + std::to_string(getpid()) + ".events");
    class_bytes.open(directory + "/" + std::to_string(getpid()) + ".classes",std::ios::binary);
    if (!out || !class_bytes || vm->GetEnv(reinterpret_cast<void**>(&ti),JVMTI_VERSION_1_2) != JNI_OK) return JNI_ERR;
    jvmtiCapabilities cap{};
    cap.can_tag_objects = cap.can_generate_breakpoint_events = cap.can_generate_frame_pop_events = 1;
    cap.can_access_local_variables = cap.can_generate_all_class_hook_events = 1;
    if (ti->AddCapabilities(&cap) != JVMTI_ERROR_NONE) return JNI_ERR;
    jvmtiEventCallbacks events{};
    events.ClassFileLoadHook = loaded; events.ClassPrepare = prepared;
    events.Breakpoint = hit; events.FramePop = returned; events.VMDeath = ended;
    if (ti->SetEventCallbacks(&events,sizeof(events)) != JVMTI_ERROR_NONE) return JNI_ERR;
    for (auto event : {JVMTI_EVENT_CLASS_FILE_LOAD_HOOK, JVMTI_EVENT_CLASS_PREPARE, JVMTI_EVENT_BREAKPOINT,
                       JVMTI_EVENT_FRAME_POP, JVMTI_EVENT_VM_DEATH})
        if (ti->SetEventNotificationMode(JVMTI_ENABLE,event,nullptr) != JVMTI_ERROR_NONE) return JNI_ERR;
    return JNI_OK;
}
