/* Testbed V2 — Tier 0 Pure C++ Fusion 케이스 (11개).
 *
 * 각 케이스는 09_tdo_testbed가 단일 기능으로 이미 검증한 패턴들을
 * 하나의 large/nested struct 흐름에 "융합"한 경우만 다룬다.
 * anchor = dfb_sink_int 호출의 arg0. 정답은 manifests/cases_v2_manifest.json 참조.
 */

#include <cstring>
#include "tv2_types.h"
#include "tv2_sources_sinks.h"

extern "C" {

/* TV2C001 — LargeStructCopy: B=A 후 narrow field demand 보존. expect A / forbid B */
TV2_CASE void case_TV2C001_large_struct_copy(void) {
    FTraceLargeLike A; std::memset(&A, 0, sizeof A);
    FTraceLargeLike B; std::memset(&B, 0, sizeof B);
    A.Inner.Secret = dfb_source_A();
    A.Other        = dfb_source_B();
    B = A;
    dfb_sink_int(B.Inner.Secret);
}

/* TV2C002 — DeepNested 4-depth: A.Transform.Translation.X. expect A / forbid B */
TV2_CASE void case_TV2C002_deep_nested(void) {
    FTraceLargeLike A; std::memset(&A, 0, sizeof A);
    A.Transform.Translation.X = (float)dfb_source_A();
    A.Transform.Rotation.Y    = (float)dfb_source_B();
    dfb_sink_int((int)A.Transform.Translation.X);
}

/* TV2C004 — ControlVsDataStructPhi: 값은 data{A,B}, 분기조건은 control{C}.
 *           data expect A,B / control expect C / data forbid C */
TV2_CASE void case_TV2C004_control_vs_data_struct_phi(void) {
    FTraceLargeLike B; std::memset(&B, 0, sizeof B);
    int cond = dfb_source_C();
    if (cond) B.Inner.Secret = dfb_source_A();
    else      B.Inner.Secret = dfb_source_B();
    dfb_sink_int(B.Inner.Secret);
}

/* TV2C005 — PartialOverwriteKill: 복사 후 같은 슬롯 덮어쓰기. expect C / forbid A,B */
TV2_CASE void case_TV2C005_partial_overwrite_kill(void) {
    FTraceLargeLike A; std::memset(&A, 0, sizeof A);
    FTraceLargeLike B; std::memset(&B, 0, sizeof B);
    A.Inner.Secret = dfb_source_A();
    A.Other        = dfb_source_B();
    B = A;
    B.Inner.Secret = dfb_source_C();   /* strong-update: 옛 source(A) 죽음 */
    dfb_sink_int(B.Inner.Secret);
}

/* TV2C006 — WideCopyNarrowForbidden: 복사 후 다른 슬롯에 B. expect B / forbid A */
TV2_CASE void case_TV2C006_wide_copy_narrow_forbidden(void) {
    FTraceLargeLike A; std::memset(&A, 0, sizeof A);
    FTraceLargeLike B; std::memset(&B, 0, sizeof B);
    A.Inner.Secret = dfb_source_A();   /* Inner만 A로 오염 */
    B = A;
    B.Other = dfb_source_B();          /* Other만 B로 오염 */
    dfb_sink_int(B.Other);             /* A가 Other로 번지면 FAIL */
}

/* TV2C011 — IntraProcPointerChain: 함수 내 3단 indirection. expect A / forbid B */
TV2_CASE void case_TV2C011_intra_proc_pointer_chain(void) {
    FTraceInnerLike leaf; std::memset(&leaf, 0, sizeof leaf);
    leaf.Secret = dfb_source_A();
    leaf.Noise  = dfb_source_B();
    FTraceInnerLike*   p1 = &leaf;
    FTraceInnerLike**  p2 = &p1;
    FTraceInnerLike*** p3 = &p2;
    dfb_sink_int((***p3).Secret);
}

/* TV2C012 — RefAliasIntoField: reference 별칭이 large-struct 슬롯 갱신. expect A / forbid B */
TV2_CASE void case_TV2C012_ref_alias_into_field(void) {
    FTraceLargeLike A; std::memset(&A, 0, sizeof A);
    int& r = A.Inner.Secret;
    r = dfb_source_A();
    A.Inner.Noise = dfb_source_B();
    dfb_sink_int(A.Inner.Secret);
}

/* TV2C013 — SubStructMemcpy: Inner sub-struct만 부분 복사. expect A / forbid B */
TV2_CASE void case_TV2C013_sub_struct_memcpy(void) {
    FTraceLargeLike A; std::memset(&A, 0, sizeof A);
    FTraceLargeLike B; std::memset(&B, 0, sizeof B);
    A.Inner.Secret = dfb_source_A();
    A.Other        = dfb_source_B();
    std::memcpy(&B.Inner, &A.Inner, sizeof(A.Inner));  /* Other는 복사 안 됨 */
    dfb_sink_int(B.Inner.Secret);
}

/* TV2C017 — DiamondPhiFieldSplit: 분기마다 다른 field. sink(Secret) → expect A / forbid B */
TV2_CASE void case_TV2C017_diamond_phi_field_split(void) {
    FTraceInnerLike s; std::memset(&s, 0, sizeof s);
    int cond = dfb_source_C();
    if (cond) s.Secret = dfb_source_A();
    else      s.Noise  = dfb_source_B();   /* B는 Noise로만 → Secret sink에 와선 안 됨 */
    dfb_sink_int(s.Secret);
}

/* TV2C018 — CallOutMemMutate: helper가 포인터로 한 field만 set. expect A / forbid B */
TV2_HELPER void tv2_set_secret(FTraceLargeLike* o, int v) { o->Inner.Secret = v; }

TV2_CASE void case_TV2C018_call_out_mem_mutate(void) {
    FTraceLargeLike A; std::memset(&A, 0, sizeof A);
    tv2_set_secret(&A, dfb_source_A());
    A.Other = dfb_source_B();
    dfb_sink_int(A.Inner.Secret);
}

/* TV2C020 — VeryLargeStruct(16KB+): 거대 struct copy + distinct field. expect A / forbid B */
TV2_CASE void case_TV2C020_very_large_struct(void) {
    FHugeLike A; std::memset(&A, 0, sizeof A);
    A.Fields[10] = dfb_source_A();
    A.Fields[20] = dfb_source_B();
    FHugeLike B; B = A;
    dfb_sink_int(B.Fields[10]);
}


/* TV2C501 — Nested memcpy + pointer-to-field demand. expect A / forbid B,C */
struct TV2x501_Leaf {
    int hot;
    int cold;
};

struct TV2x501_Outer {
    TV2x501_Leaf left;
    TV2x501_Leaf right;
};

TV2_CASE void case_TV2C501_nested_memcpy_field_ptr_neighbor(void) {
    TV2x501_Outer src = {};
    TV2x501_Outer dst = {};
    src.left.hot = dfb_source_A();
    src.left.cold = dfb_source_B();
    src.right.hot = dfb_source_C();

    std::memcpy(&dst, &src, sizeof(dst));

    int *p = &dst.left.hot;
    dfb_sink_int(*p);
}


/* TV2C502 — Subobject copy + partial overwrite kill. expect B / forbid A,C */
struct TV2x502_Inner {
    int keep;
    int killed;
};

struct TV2x502_Box {
    int prefix;
    TV2x502_Inner inner;
    int tail;
};

TV2_HELPER void tv2x502_copy_inner(TV2x502_Inner *dst, const TV2x502_Inner *src) {
    *dst = *src;
}

TV2_CASE void case_TV2C502_nested_assignment_partial_overwrite_kill(void) {
    TV2x502_Box src = {};
    TV2x502_Box dst = {};
    src.prefix = dfb_source_A();
    src.inner.keep = dfb_source_B();
    src.inner.killed = dfb_source_C();

    tv2x502_copy_inner(&dst.inner, &src.inner);
    dst.inner.killed = 0;

    int *p = &dst.inner.keep;
    dfb_sink_int(*p);
}


/* TV2C601 - Indirect helper writes selected field. expect A / forbid B,C */
struct TV2x601_Cell {
    int payload;
    int noise;
};

struct TV2x601_Box {
    TV2x601_Cell cells[3];
};

typedef void (*TV2x601_Callback)(TV2x601_Box *);

TV2_HELPER void tv2x601_write_expected(TV2x601_Box *box) {
    box->cells[1].payload = dfb_source_A();
}

TV2_HELPER void tv2x601_write_neighbor(TV2x601_Box *box) {
    box->cells[0].noise = dfb_source_B();
}

TV2_CASE void case_TV2C601_indirect_callback_field_write(void) {
    TV2x601_Box box = {};
    TV2x601_Callback callbacks[2] = {
        tv2x601_write_neighbor,
        tv2x601_write_expected,
    };

    callbacks[1](&box);
    box.cells[2].payload = dfb_source_C();

    int *p = &box.cells[1].payload;
    dfb_sink_int(*p);
}


/* TV2C602 - Global pointer selected through helper + loop noise. expect B / forbid A,C */
struct TV2x602_Node {
    int value;
    int noise;
};

struct TV2x602_Graph {
    TV2x602_Node nodes[4];
};

static TV2x602_Node *g_tv2x602_selected = 0;

TV2_HELPER void tv2x602_select_node(TV2x602_Graph *graph, int index) {
    g_tv2x602_selected = &graph->nodes[index];
}

TV2_CASE void case_TV2C602_global_pointer_loop_phi(void) {
    TV2x602_Graph graph = {};
    graph.nodes[0].value = dfb_source_A();
    graph.nodes[2].value = dfb_source_B();
    graph.nodes[3].noise = dfb_source_C();

    tv2x602_select_node(&graph, 2);

    for (int i = 0; i < 4; ++i) {
        if (i != 2) {
            graph.nodes[i].noise = i;
        }
    }

    dfb_sink_int(g_tv2x602_selected->value);
}


/* TV2C603 - Indirect callback after aggregate clear. expect A / forbid B */
struct TV2C603_Cell { int expected; int neighbor; };
struct TV2C603_CallbackTable { void (*store)(TV2C603_Cell*, int); };

TV2_HELPER void tv2c603_store_expected(TV2C603_Cell* cell, int value) {
    cell->expected = value;
}

TV2_HELPER void tv2c603_store_neighbor(TV2C603_Cell* cell, int value) {
    cell->neighbor = value;
}

TV2_CASE void case_TV2C603_indirect_callback_after_vector_clear(void) {
    TV2C603_Cell cell;
    std::memset(&cell, 0, sizeof cell);
    TV2C603_CallbackTable table = { tv2c603_store_expected };
    volatile TV2C603_CallbackTable* chosen = &table;
    int tainted = dfb_source_A();
    int unrelated = dfb_source_B();
    chosen->store(&cell, tainted);
    tv2c603_store_neighbor(&cell, unrelated);
    dfb_sink_int(cell.expected);
}


/* TV2C604 — Indirect callback writes A into target after aggregate clear.
 *           expect A / forbid B and pre-callback zero clear.
 */

struct TV2C604_State { int keep; int target; int neighbor; };
using TV2C604_Callback = void (*)(TV2C604_State*, int, int);

static void tv2c604_write_target(TV2C604_State* s, int value, int noise) {
    s->target = value;
    s->neighbor = noise ^ 0x5a5a5a5a;
}

TV2_CASE void case_TV2C604_indirect_callback_field_write_vector_clear(void) {
    TV2C604_State st{};
    TV2C604_Callback table[2] = {tv2c604_write_target, tv2c604_write_target};
    int a = dfb_source_A();
    int b = dfb_source_B();
    table[(b & 1) ^ (b & 1)](&st, a, b);
    dfb_sink_int(st.target);
}

/* TV2C605 - Offline local case-author seed.
 *           expect A / forbid B,C
 */
struct TV2C605_Cell {
    int target;
    int neighbor;
    int killed;
};

struct TV2C605_Box {
    TV2C605_Cell cells[2];
    int guard;
};

typedef void (*TV2C605_Writer)(TV2C605_Box*, int, int);

TV2_HELPER void tv2c605_write_target(TV2C605_Box *box, int value, int noise) {
    box->cells[1].target = value;
    box->cells[0].neighbor = noise;
}

TV2_HELPER void tv2c605_overwrite_neighbor(TV2C605_Box *box, int value) {
    box->cells[1].neighbor = value;
}

TV2_CASE void case_TV2C605_offline_indirect_field_loop_guard(void) {
    TV2C605_Box box = {};
    TV2C605_Writer writers[2] = {
        tv2c605_write_target,
        tv2c605_write_target,
    };
    int a = dfb_source_A();
    int b = dfb_source_B();
    int c = dfb_source_C();

    for (int i = 0; i < 2; ++i) {
        box.cells[i].neighbor = b + i;
    }

    writers[(c & 1) ^ (c & 1)](&box, a, c);
    tv2c605_overwrite_neighbor(&box, b);
    box.cells[1].killed = c;

    dfb_sink_int(box.cells[1].target);
}


struct TV2C606Lane { int pad; int value; int shadow; };
struct TV2C606Box { TV2C606Lane lanes[4]; int tail; };
using TV2C606Writer = void (*)(TV2C606Box*, int, int);
TV2_HELPER void tv2c606_write_live(TV2C606Box* box, int idx, int v) { box->lanes[idx].value = v; }
TV2_HELPER void tv2c606_write_dead(TV2C606Box* box, int idx, int v) { box->lanes[idx].shadow = v; }
TV2_CASE void case_TV2C606_callback_heap_lane_overwrite(void) {
    TV2C606Box* box = new TV2C606Box{};
    int live = dfb_source_A();
    int dead = dfb_source_B();
    int noise = dfb_source_C();
    TV2C606Writer writer = tv2c606_write_live;
    TV2C606Writer decoy = tv2c606_write_dead;
    for (int i = 0; i < 4; ++i) {
        box->lanes[i].value = noise + i;
        box->lanes[i].shadow = dead + i;
    }
    decoy(box, 2, dead);
    writer(box, 2, live);
    box->lanes[2].shadow = 0;
    TV2C606Lane* lane = reinterpret_cast<TV2C606Lane*>(reinterpret_cast<char*>(box->lanes) + 2 * sizeof(TV2C606Lane));
    dfb_sink_int(lane->value);
    delete box;
}


struct TV2C607Item { int key; int payload; int stale; };
struct TV2C607Vec { TV2C607Item* data; int count; };
using TV2C607Mutator = void (*)(TV2C607Vec*, int, int);
TV2_HELPER void tv2c607_set_payload(TV2C607Vec* vec, int idx, int v) { vec->data[idx].payload = v; }
TV2_HELPER void tv2c607_set_stale(TV2C607Vec* vec, int idx, int v) { vec->data[idx].stale = v; }
TV2_CASE void case_TV2C607_container_alias_callback_kill(void) {
    TV2C607Item storage[5] = {};
    TV2C607Vec view{storage + 1, 3};
    int live = dfb_source_A();
    int stale = dfb_source_B();
    int neighbor = dfb_source_C();
    for (int i = 0; i < view.count; ++i) {
        view.data[i].payload = neighbor + i;
        view.data[i].stale = stale + i;
    }
    TV2C607Mutator fp = tv2c607_set_stale;
    fp(&view, 1, stale);
    fp = tv2c607_set_payload;
    fp(&view, 1, live);
    TV2C607Item* alias = reinterpret_cast<TV2C607Item*>(reinterpret_cast<char*>(view.data) + sizeof(TV2C607Item));
    alias->stale = 0;
    storage[0].payload = neighbor;
    storage[4].payload = stale;
    dfb_sink_int(alias->payload);
}


struct TV2C608_Cell { int lane0; int lane1; int lane2; };
struct TV2C608_Box { TV2C608_Cell* primary; TV2C608_Cell* alias; };
using TV2C608_Callback = void (*)(TV2C608_Box*, int);
static void tv2c608_write_alias_lane1(TV2C608_Box* box, int v) { TV2C608_Cell* p = box->alias; p->lane1 = v; }
extern "C" void case_TV2C608_loaded_alias_callback_preserve_neighbor() {
  TV2C608_Cell* cell = new TV2C608_Cell{dfb_source_B(), 0, dfb_source_C()};
  TV2C608_Box box{cell, cell};
  TV2C608_Callback cb = tv2c608_write_alias_lane1;
  cb(&box, dfb_source_A());
  int observed = box.primary->lane1;
  dfb_sink_int(observed);
  delete cell;
}


struct TV2C609Cell { int lane0; int lane1; int lane2; };
using TV2C609Write = void (*)(TV2C609Cell *, int);
static void tv2c609_store_lane1(TV2C609Cell *cell, int v) { cell->lane1 = v; }
static void tv2c609_store_lane2(TV2C609Cell *cell, int v) { cell->lane2 = v; }
extern "C" void case_TV2C609_loaded_pointer_callback_neighbor_guard() {
  TV2C609Cell *cell = new TV2C609Cell{0, 0, 0};
  TV2C609Write cb = tv2c609_store_lane1;
  int tainted = dfb_source_A();
  int noise = dfb_source_B();
  TV2C609Cell **slot = &cell;
  (*cb)(*slot, tainted);
  tv2c609_store_lane2(*slot, noise);
  int observed = (*slot)->lane1;
  dfb_sink_int(observed);
  delete cell;
}


struct TV2C610_Cell { int guard0; int payload; int guard1; };
using TV2C610_Callback = void (*)(TV2C610_Cell*, int);

extern "C" TV2_NOINLINE void tv2c610_write_payload_thunk(TV2C610_Cell* cell, int value) {
    cell->payload = value;
}

extern "C" TV2_NOINLINE void case_TV2C610_callback_heap_payload_overwrite_strict() {
    TV2C610_Cell* cell = new TV2C610_Cell{dfb_source_B(), 0, dfb_source_B()};
    TV2C610_Callback cb = tv2c610_write_payload_thunk;
    int a = dfb_source_A();
    cb(cell, a);
    dfb_sink_int(cell->payload);
    delete cell;
}


struct TV2C611_Box { int left; int mid; int right; };
struct TV2C611_View { TV2C611_Box* primary; TV2C611_Box* alias; };
using TV2C611_Kill = void (*)(TV2C611_View*, int);

extern "C" TV2_NOINLINE void tv2c611_alias_kill_thunk(TV2C611_View* view, int value) {
    view->alias->mid = value;
}

extern "C" TV2_NOINLINE void case_TV2C611_container_alias_callback_kill_strict() {
    TV2C611_Box box{dfb_source_B(), dfb_source_B(), dfb_source_B()};
    TV2C611_View view{&box, &box};
    TV2C611_Kill kill = tv2c611_alias_kill_thunk;
    int a = dfb_source_A();
    kill(&view, a);
    dfb_sink_int(view.primary->mid);
}


struct TV2C612Slot {
    int (*callback)(int);
    int payload;
    int decoy;
};

TV2_NOINLINE static int tv2c612_use_a(int v) {
    return (v ^ 0x13579) + 7;
}

TV2_NOINLINE static int tv2c612_use_b(int v) {
    return (v * 3) - 11;
}

TV2_NOINLINE static int tv2c612_invoke(TV2C612Slot* slot) {
    int mixed = slot->callback(slot->payload);
    return mixed + (slot->decoy & 0);
}

extern "C" TV2_NOINLINE void case_TV2C612_computed_callback_struct_overwrite(void) {
    TV2C612Slot slot;
    slot.callback = tv2c612_use_b;
    slot.payload = dfb_source_B();
    slot.decoy = dfb_source_C();
    slot.callback = tv2c612_use_a;
    slot.payload = dfb_source_A();
    int out = tv2c612_invoke(&slot);
    dfb_sink_int(out);
}


struct TV2C613_Box {
    int live;
    int dead;
    int guard;
};

typedef void (*TV2C613_Callback)(TV2C613_Box*, int, int);

TV2_NOINLINE void TV2C613_write_live_from_first(TV2C613_Box* box, int first, int second) {
    box->live = (first ^ 0x13579bdf) + 3;
    box->dead = second;
}

TV2_NOINLINE void TV2C613_write_live_from_second(TV2C613_Box* box, int first, int second) {
    box->live = second + 17;
    box->dead = first;
}

TV2_NOINLINE void TV2C613_dispatch(TV2C613_Callback cb, TV2C613_Box* box, int x, int y) {
    cb(box, x, y);
}

extern "C" TV2_NOINLINE void case_TV2C613_computed_callback_field_kill() {
    int a = dfb_source_A();
    int b = dfb_source_B();
    int c = dfb_source_C();
    TV2C613_Box box = {0, 0, 0};
    TV2C613_Callback callbacks[2] = {TV2C613_write_live_from_second, TV2C613_write_live_from_first};
    volatile unsigned lane = 1u;
    unsigned idx = lane & 1u;
    TV2C613_dispatch(callbacks[idx], &box, a, b);
    box.dead = c;
    dfb_sink_int(box.live);
}


struct TV2C614_Box {
    int live;
    int dead;
};

typedef void (*TV2C614_WriteFn)(TV2C614_Box*, int, int);

TV2_NOINLINE static void TV2C614_write_live(TV2C614_Box* box, int live_value, int noise_value) {
    box->dead = noise_value;
    box->live = live_value;
}

TV2_NOINLINE static void TV2C614_write_dead(TV2C614_Box* box, int live_value, int noise_value) {
    box->live = noise_value;
    box->dead = live_value;
}

extern "C" TV2_NOINLINE void case_TV2C614_computed_callback_field_kill(void) {
    TV2C614_Box box;
    box.live = dfb_source_B();
    box.dead = dfb_source_C();

    int selector = (dfb_source_C() ^ 0x55) & 1;
    TV2C614_WriteFn table[2] = {TV2C614_write_live, TV2C614_write_dead};
    TV2C614_WriteFn writer = table[selector ^ selector];

    int live_value = dfb_source_A();
    int noise_value = dfb_source_C();
    writer(&box, live_value, noise_value);

    dfb_sink_int(box.live);
}


struct TV2C615_Node {
  int lane0;
  int lane1;
};

using TV2C615_Callback = int (*)(TV2C615_Node *node, int noise);

TV2_NOINLINE static int TV2C615_write_a_lane1(TV2C615_Node *node, int noise) {
  node->lane1 = dfb_source_A() ^ 0x6151;
  node->lane0 = noise;
  return node->lane1;
}

TV2_NOINLINE static int TV2C615_write_b_lane0(TV2C615_Node *node, int noise) {
  node->lane0 = dfb_source_B() ^ noise;
  return node->lane0;
}

extern "C" TV2_NOINLINE void case_TV2C615_callback_table_field_lane_precise(void) {
  TV2C615_Node node = {0, 0};
  TV2C615_Callback table[2] = {TV2C615_write_a_lane1, TV2C615_write_b_lane0};
  int selector = (dfb_source_C() & 1) ^ 1;
  int noise = dfb_source_C() | 0x20;
  table[selector](&node, noise);
  int value = node.lane1;
  dfb_sink_int(value);
}


struct TV2C616_Node {
    int value;
    int noise;
    TV2C616_Node* next;
};

typedef void (*TV2C616_Callback)(TV2C616_Node*, int);

TV2_NOINLINE void tv2c616_write_selected_lane(TV2C616_Node* node, int v) {
    if ((v & 1) != 0) {
        node->value = v;
    } else {
        node->noise = dfb_source_C();
        node->value = v + 1;
    }
}

TV2_NOINLINE void tv2c616_write_noise_lane(TV2C616_Node* node, int v) {
    node->noise = v;
}

extern "C" TV2_NOINLINE void case_TV2C616_callback_field_kill_precise(void) {
    TV2C616_Node first = {0, 0, 0};
    TV2C616_Node second = {0, 0, 0};
    first.next = &second;
    second.next = &first;

    int live = dfb_source_A();
    int dead = dfb_source_B();
    TV2C616_Callback cb = ((live ^ 0x1357) & 1) ? tv2c616_write_selected_lane : tv2c616_write_selected_lane;
    TV2C616_Callback noise_cb = tv2c616_write_noise_lane;

    noise_cb(first.next, dead);
    cb(first.next, live);
    dfb_sink_int(second.value);
}


struct TV2C617_Cell {
    int tag;
    int payload;
    int decoy;
};

typedef int (*TV2C617_LoadFn)(TV2C617_Cell *);

static TV2_NOINLINE int TV2C617_load_payload(TV2C617_Cell *cell) {
    return cell->payload;
}

static TV2_NOINLINE int TV2C617_load_decoy(TV2C617_Cell *cell) {
    return cell->decoy;
}

struct TV2C617_Dispatch {
    int selector;
    TV2C617_LoadFn fn[2];
};

extern "C" TV2_NOINLINE void case_TV2C617_computed_callback_field_payload(void) {
    TV2C617_Cell cell;
    cell.tag = 0x617;
    cell.payload = dfb_source_A();
    cell.decoy = dfb_source_B();

    TV2C617_Dispatch dispatch;
    dispatch.selector = 1;
    dispatch.fn[0] = &TV2C617_load_decoy;
    dispatch.fn[1] = &TV2C617_load_payload;

    TV2C617_LoadFn chosen = dispatch.fn[dispatch.selector];
    int value = chosen(&cell);
    dfb_sink_int(value);
}


struct TV2C618_Node {
    int live;
    int stale;
};

struct TV2C618_Box {
    TV2C618_Node first;
    TV2C618_Node second;
};

static TV2_NOINLINE void TV2C618_write_second_live(TV2C618_Box *box, int value) {
    box->second.live = value;
}

static TV2_NOINLINE int TV2C618_read_second_live(TV2C618_Box *box) {
    return box->second.live;
}

extern "C" TV2_NOINLINE void case_TV2C618_nested_field_overwrite_summary(void) {
    TV2C618_Box box;
    box.first.live = dfb_source_B();
    box.first.stale = 0x1818;
    box.second.live = dfb_source_C();
    box.second.stale = 0x2828;

    TV2C618_write_second_live(&box, dfb_source_A());
    int value = TV2C618_read_second_live(&box);
    dfb_sink_int(value);
}


struct TV2C619_Box {
    int first;
    int second;
};

using TV2C619_Select = int (*)(TV2C619_Box*);

TV2_NOINLINE int tv2c619_read_second(TV2C619_Box* box) {
    return box->second;
}

TV2_NOINLINE int tv2c619_read_first(TV2C619_Box* box) {
    return box->first;
}

extern "C" TV2_NOINLINE void case_TV2C619_computed_callback_field_kill(void) {
    TV2C619_Box box;
    box.first = dfb_source_B();
    box.second = dfb_source_A();
    box.first = 0x6191;

    volatile int choose = 1;
    TV2C619_Select fp = choose ? tv2c619_read_second : tv2c619_read_first;
    int value = fp(&box);
    dfb_sink_int(value);
}


struct TV2C620_State {
    int lane[3];
};

TV2_NOINLINE void tv2c620_store_lane(TV2C620_State* state, int index, int value) {
    state->lane[index] = value;
}

TV2_NOINLINE int tv2c620_load_lane(TV2C620_State* state, int index) {
    return state->lane[index];
}

extern "C" TV2_NOINLINE void case_TV2C620_interproc_indexed_field_summary_kill(void) {
    TV2C620_State state;
    tv2c620_store_lane(&state, 0, dfb_source_A());
    tv2c620_store_lane(&state, 1, dfb_source_B());
    tv2c620_store_lane(&state, 0, 0x6200);

    volatile int idx = 1;
    int value = tv2c620_load_lane(&state, idx);
    dfb_sink_int(value);
}


struct TV2C621_Node {
    int live;
    int noise;
};

typedef void (*TV2C621_Writer)(TV2C621_Node *, int);

TV2_NOINLINE void tv2c621_write_live(TV2C621_Node *n, int v) {
    n->live = v;
}

TV2_NOINLINE void tv2c621_write_noise(TV2C621_Node *n, int v) {
    n->noise = v;
}

TV2_NOINLINE TV2C621_Writer tv2c621_select_writer(int selector) {
    volatile int guard = selector ^ 0x621;
    if ((guard ^ 0x621) == 1) {
        return tv2c621_write_noise;
    }
    return tv2c621_write_live;
}

extern "C" TV2_NOINLINE void case_TV2C621_computed_writer_field_kill() {
    TV2C621_Node node;
    node.live = dfb_source_A();
    node.noise = dfb_source_B();
    TV2C621_Writer writer = tv2c621_select_writer(0);
    writer(&node, dfb_source_C());
    dfb_sink_int(node.live);
}


struct TV2C622_Cell { int live; int decoy; };

typedef int (*TV2C622_ReadFn)(TV2C622_Cell*);
typedef void (*TV2C622_WriteFn)(TV2C622_Cell*, int);

TV2_NOINLINE static void tv2c622_write_live(TV2C622_Cell* cell, int value) {
  cell->live = value;
}

TV2_NOINLINE static void tv2c622_write_decoy(TV2C622_Cell* cell, int value) {
  cell->decoy = value;
}

TV2_NOINLINE static int tv2c622_read_live(TV2C622_Cell* cell) {
  return cell->live;
}

TV2_NOINLINE static int tv2c622_read_decoy(TV2C622_Cell* cell) {
  return cell->decoy;
}

TV2_NOINLINE static TV2C622_WriteFn tv2c622_pick_writer(int selector) {
  return selector ? tv2c622_write_live : tv2c622_write_decoy;
}

TV2_NOINLINE static TV2C622_ReadFn tv2c622_pick_reader(int selector) {
  return selector ? tv2c622_read_live : tv2c622_read_decoy;
}

extern "C" TV2_NOINLINE void case_TV2C622_computed_write_then_computed_read_field_precise(void) {
  TV2C622_Cell cell;
  cell.live = dfb_source_B();
  cell.decoy = dfb_source_C();

  TV2C622_WriteFn write_live = tv2c622_pick_writer(1);
  TV2C622_ReadFn read_live = tv2c622_pick_reader(1);
  TV2C622_ReadFn read_decoy = tv2c622_pick_reader(0);

  write_live(&cell, dfb_source_A());
  int noise = read_decoy(&cell);
  int value = read_live(&cell) ^ (noise & 0);
  dfb_sink_int(value);
}


struct TV2C623_Node {
    int lane0;
    int lane1;
    int noise;
};

using TV2C623_Writer = void (*)(TV2C623_Node *, int, int);

TV2_NOINLINE static void tv2c623_write_lane0(TV2C623_Node *n, int value, int decoy) {
    n->lane0 = value;
    n->noise = decoy ^ 0x6230;
}

TV2_NOINLINE static void tv2c623_write_lane1(TV2C623_Node *n, int value, int decoy) {
    n->lane1 = value;
    n->noise = decoy + 0x17;
}

TV2_NOINLINE static TV2C623_Writer tv2c623_pick_writer(int selector) {
    return (selector & 1) ? &tv2c623_write_lane1 : &tv2c623_write_lane0;
}

extern "C" TV2_NOINLINE void case_TV2C623_computed_writer_field_kill(void) {
    TV2C623_Node node = {0, 0, 0};
    int live = dfb_source_A();
    int killed = dfb_source_B();
    int decoy = dfb_source_C();
    node.lane0 = killed;
    TV2C623_Writer writer = tv2c623_pick_writer(0);
    writer(&node, live, decoy);
    dfb_sink_int(node.lane0);
}


struct TV2C624_Node {
    int tag;
    int live;
    int decoy;
};

typedef void (*TV2C624_Callback)(TV2C624_Node*, int);

TV2_NOINLINE static void tv2c624_store_live(TV2C624_Node* n, int v) {
    n->live = v ^ 0x1357;
}

TV2_NOINLINE static void tv2c624_store_decoy(TV2C624_Node* n, int v) {
    n->decoy = v + 0x2468;
}

extern "C" TV2_NOINLINE void case_TV2C624_computed_callback_field_kill(void) {
    TV2C624_Node n;
    n.tag = 1;
    n.live = dfb_source_C();
    n.decoy = dfb_source_B();
    TV2C624_Callback table[2] = { tv2c624_store_decoy, tv2c624_store_live };
    TV2C624_Callback cb = table[n.tag & 1];
    cb(&n, dfb_source_A());
    n.decoy = 0x4040;
    dfb_sink_int(n.live);
}


struct TV2C625_Box {
    int live;
    int decoy;
};

typedef void (*TV2C625_WriteFn)(TV2C625_Box*, int);

static TV2_NOINLINE void TV2C625_write_live(TV2C625_Box* box, int value) {
    box->live = value;
}

static TV2_NOINLINE void TV2C625_write_decoy(TV2C625_Box* box, int value) {
    box->decoy = value;
}

static TV2_NOINLINE TV2C625_WriteFn TV2C625_pick_writer(int tag) {
    volatile int stable_tag = tag;
    if ((stable_tag & 3) == 1) {
        return &TV2C625_write_live;
    }
    return &TV2C625_write_decoy;
}

extern "C" TV2_NOINLINE void case_TV2C625_computed_callback_field_kill() {
    TV2C625_Box box;
    box.live = dfb_source_B();
    box.decoy = dfb_source_C();

    TV2C625_WriteFn writer = TV2C625_pick_writer(1);
    int live_value = dfb_source_A();
    int decoy_value = dfb_source_B();
    writer(&box, live_value);
    box.decoy = decoy_value;

    int out = box.live;
    dfb_sink_int(out);
}


struct TV2C626_Cell {
    int live;
    int decoy;
};

typedef int (*TV2C626_ReadFn)(TV2C626_Cell *cell);

TV2_NOINLINE int TV2C626_read_live(TV2C626_Cell *cell) {
    return cell->live;
}

TV2_NOINLINE int TV2C626_read_decoy(TV2C626_Cell *cell) {
    return cell->decoy;
}

TV2_NOINLINE void case_TV2C626_computed_callback_field_kill(void) {
    TV2C626_Cell cell;
    cell.live = dfb_source_A();
    cell.decoy = dfb_source_B();
    cell.live = dfb_source_C();

    TV2C626_ReadFn readers[2];
    readers[0] = TV2C626_read_live;
    readers[1] = TV2C626_read_decoy;

    unsigned selector = ((unsigned)cell.live ^ 0x5a5a5a5au) & 0u;
    int value = readers[selector](&cell);
    dfb_sink_int(value);
}


struct TV2C627_Node {
    int lane0;
    int lane1;
};

struct TV2C627_Box {
    TV2C627_Node node;
    int noise;
};

typedef int (*TV2C627_ReadFn)(const TV2C627_Box*);

static TV2_NOINLINE int TV2C627_read_lane1(const TV2C627_Box* box) {
    return box->node.lane1;
}

static TV2_NOINLINE int TV2C627_read_noise(const TV2C627_Box* box) {
    return box->noise;
}

static TV2_NOINLINE TV2C627_ReadFn TV2C627_pick_reader(int selector) {
    static TV2C627_ReadFn readers[2] = { TV2C627_read_noise, TV2C627_read_lane1 };
    return readers[selector & 1];
}

extern "C" TV2_NOINLINE void case_TV2C627_computed_callback_field_overwrite(void) {
    TV2C627_Box box;
    box.node.lane0 = dfb_source_A();
    box.node.lane1 = dfb_source_B();
    box.noise = dfb_source_C();
    box.node.lane0 = 0x6270;
    TV2C627_ReadFn fn = TV2C627_pick_reader(1);
    int value = fn(&box);
    dfb_sink_int(value);
}


struct TV2C628_Frame {
    int live;
    int noise;
    int guard;
};

typedef void (*TV2C628_Callback)(TV2C628_Frame*);

TV2_NOINLINE static void tv2c628_write_live(TV2C628_Frame* frame) {
    int a = dfb_source_A();
    int b = dfb_source_B();
    frame->noise = b;
    frame->live = a;
    frame->noise = 0x6280;
}

TV2_NOINLINE static void tv2c628_write_decoy(TV2C628_Frame* frame) {
    int c = dfb_source_C();
    frame->noise = c;
}

extern "C" TV2_NOINLINE void case_TV2C628_computed_callback_field_kill(void) {
    TV2C628_Frame frame = {0, 0, 0};
    TV2C628_Callback table[2] = {tv2c628_write_decoy, tv2c628_write_live};
    TV2C628_Callback cb = table[1];
    cb(&frame);
    frame.live ^= frame.guard;
    dfb_sink_int(frame.live);
}


struct TV2C629Slot {
    int first;
    int second;
};

using TV2C629Writer = void (*)(TV2C629Slot*, int);

TV2_NOINLINE void tv2c629_write_first(TV2C629Slot* slot, int value) {
    slot->first = value;
}

TV2_NOINLINE void tv2c629_write_second_noise(TV2C629Slot* slot, int value) {
    slot->second = value;
}

TV2_NOINLINE TV2C629Writer tv2c629_pick_writer(int selector) {
    volatile int guard = selector ^ 0x629;
    return (guard == 0x629) ? tv2c629_write_first : tv2c629_write_second_noise;
}

extern "C" TV2_NOINLINE void case_TV2C629_computed_writer_field_kill(void) {
    TV2C629Slot slot = {0, 0};
    int live = dfb_source_A();
    int noise = dfb_source_B();
    TV2C629Writer writer = tv2c629_pick_writer(0);
    tv2c629_write_second_noise(&slot, noise);
    writer(&slot, live);
    dfb_sink_int(slot.first);
}


struct TV2C630_Cell {
  int tag;
  int live;
  int decoy;
};

using TV2C630_Thunk = int (*)(TV2C630_Cell *);

TV2_NOINLINE int tv2c630_read_live(TV2C630_Cell *cell) {
  return cell->live;
}

TV2_NOINLINE int tv2c630_read_decoy(TV2C630_Cell *cell) {
  return cell->decoy;
}

TV2_NOINLINE TV2C630_Thunk tv2c630_pick_reader(int selector) {
  volatile int guard = selector ^ 0x5a5a;
  if ((guard & 1) == 0) {
    return &tv2c630_read_live;
  }
  return &tv2c630_read_decoy;
}

extern "C" TV2_NOINLINE void case_TV2C630_computed_reader_field_precision(void) {
  TV2C630_Cell cell;
  cell.tag = 0x630;
  cell.live = dfb_source_A();
  cell.decoy = dfb_source_B();

  TV2C630_Thunk reader = tv2c630_pick_reader(0x5a5a);
  int value = reader(&cell);
  dfb_sink_int(value);
}


struct TV2C631_Box {
    int live;
    int dead;
};

typedef void (*TV2C631_Callback)(TV2C631_Box*, int, int);

TV2_NOINLINE static void tv2c631_store_first(TV2C631_Box* box, int live, int noise) {
    box->dead = noise;
    box->live = live;
}

TV2_NOINLINE static void tv2c631_store_second(TV2C631_Box* box, int live, int noise) {
    box->live = noise;
    box->live = live;
}

TV2_NOINLINE static TV2C631_Callback tv2c631_pick_callback(int selector) {
    volatile int keep = selector ^ 0x5a5a;
    if ((keep & 1) != 0) {
        return tv2c631_store_first;
    }
    return tv2c631_store_second;
}

extern "C" TV2_NOINLINE void case_TV2C631_callback_field_overwrite_dispatch(void) {
    TV2C631_Box box;
    box.live = 0;
    box.dead = dfb_source_C();
    int live = dfb_source_A();
    int noise = dfb_source_B();
    TV2C631_Callback cb = tv2c631_pick_callback(live);
    cb(&box, live, noise);
    dfb_sink_int(box.live);
}


struct TV2C632_Node {
  int decoy;
  int live;
  int shadow;
};

typedef void (*TV2C632_WriteFn)(TV2C632_Node*);
typedef int (*TV2C632_ReadFn)(TV2C632_Node*);

TV2_NOINLINE static void tv2c632_write_decoy(TV2C632_Node* n) {
  n->decoy = dfb_source_B();
}

TV2_NOINLINE static void tv2c632_write_live(TV2C632_Node* n) {
  n->live = dfb_source_A();
}

TV2_NOINLINE static int tv2c632_read_live(TV2C632_Node* n) {
  return n->live;
}

TV2_NOINLINE static int tv2c632_read_shadow(TV2C632_Node* n) {
  return n->shadow;
}

extern "C" TV2_NOINLINE void case_TV2C632_computed_callback_field_summary(void) {
  TV2C632_Node node;
  node.decoy = 0;
  node.live = 0;
  node.shadow = dfb_source_C();

  TV2C632_WriteFn writers[2] = { tv2c632_write_decoy, tv2c632_write_live };
  TV2C632_ReadFn readers[2] = { tv2c632_read_live, tv2c632_read_shadow };

  volatile int pick_writer = 1;
  volatile int pick_reader = 0;

  writers[pick_writer & 1](&node);
  node.decoy = 0x6320;

  int out = readers[pick_reader & 1](&node);
  dfb_sink_int(out);
}


struct TV2C633_Node {
    int value;
    int noise;
};

using TV2C633_Callback = void (*)(TV2C633_Node*, int);

static TV2_NOINLINE void tv2c633_write_value(TV2C633_Node* node, int v) {
    node->value = v;
}

static TV2_NOINLINE void tv2c633_write_noise(TV2C633_Node* node, int v) {
    node->noise = v;
}

static TV2_NOINLINE TV2C633_Callback tv2c633_pick_writer(int selector) {
    if ((selector & 1) == 0) {
        return &tv2c633_write_noise;
    }
    return &tv2c633_write_value;
}

extern "C" TV2_NOINLINE void case_TV2C633_computed_callback_field_overwrite(void) {
    TV2C633_Node node;
    node.value = dfb_source_B();
    node.noise = dfb_source_C();

    TV2C633_Callback first = tv2c633_pick_writer(1);
    TV2C633_Callback second = tv2c633_pick_writer(0);

    first(&node, dfb_source_A());
    second(&node, dfb_source_C());

    int out = node.value;
    dfb_sink_int(out);
}


struct TV2C634_Box {
    int live;
    int decoy;
};

using TV2C634_Writer = void (*)(TV2C634_Box*, int);

TV2_NOINLINE static void tv2c634_write_live(TV2C634_Box* box, int value) {
    box->live = value;
}

TV2_NOINLINE static void tv2c634_write_decoy(TV2C634_Box* box, int value) {
    box->decoy = value;
}

extern "C" TV2_NOINLINE void case_TV2C634_computed_callback_field_kill(void) {
    TV2C634_Box box = {0, 0};
    TV2C634_Writer table[2] = {tv2c634_write_decoy, tv2c634_write_live};
    int live = dfb_source_A();
    int decoy = dfb_source_B();
    table[0](&box, decoy);
    table[1](&box, live);
    box.decoy = dfb_source_C();
    dfb_sink_int(box.live);
}


struct TV2C635_Node {
    int lane0;
    int lane1;
};

using TV2C635_WriteFn = void (*)(TV2C635_Node *, int);

TV2_NOINLINE void tv2c635_write_live_lane(TV2C635_Node *node, int value) {
    node->lane1 = value;
}

TV2_NOINLINE void tv2c635_write_noise_lane(TV2C635_Node *node, int value) {
    node->lane0 = value;
}

extern "C" TV2_NOINLINE void case_TV2C635_computed_callback_field_lane(void) {
    TV2C635_Node node = {0, 0};
    TV2C635_WriteFn table[2] = {tv2c635_write_noise_lane, tv2c635_write_live_lane};
    int live = dfb_source_A();
    int noise = dfb_source_B();
    table[0](&node, noise);
    table[1](&node, live);
    dfb_sink_int(node.lane1);
}


struct TV2C636_Box { int live; int decoy; };

typedef void (*TV2C636_Callback)(TV2C636_Box*, int);

TV2_NOINLINE void tv2c636_store_live(TV2C636_Box* box, int value) {
    box->live = value;
}

TV2_NOINLINE void tv2c636_store_decoy(TV2C636_Box* box, int value) {
    box->decoy = value;
}

extern "C" TV2_NOINLINE void case_TV2C636_callback_table_field_overwrite(void) {
    TV2C636_Box box;
    box.live = dfb_source_B();
    box.decoy = dfb_source_C();
    TV2C636_Callback table[2] = { tv2c636_store_decoy, tv2c636_store_live };
    unsigned selector = (unsigned)(dfb_source_C() & 1);
    table[selector ^ selector](&box, dfb_source_C());
    table[1](&box, dfb_source_A());
    dfb_sink_int(box.live);
}


struct TV2C637_Node {
    int live;
    int dead;
};

typedef int (*TV2C637_ReadFn)(TV2C637_Node *node);

static TV2_NOINLINE int TV2C637_read_live(TV2C637_Node *node) {
    return node->live;
}

static TV2_NOINLINE int TV2C637_read_dead(TV2C637_Node *node) {
    return node->dead;
}

struct TV2C637_Dispatch {
    TV2C637_ReadFn reader;
    TV2C637_Node *payload;
};

static TV2_NOINLINE int TV2C637_invoke(TV2C637_Dispatch *dispatch) {
    return dispatch->reader(dispatch->payload);
}

extern "C" TV2_NOINLINE void case_TV2C637_computed_callback_field_kill(void) {
    TV2C637_Node node;
    node.live = dfb_source_A();
    node.dead = dfb_source_B();
    node.dead = 0x6370;

    TV2C637_Dispatch dispatch;
    dispatch.reader = TV2C637_read_live;
    dispatch.payload = &node;

    int noise = dfb_source_C();
    if ((noise & 1) == 2) {
        dispatch.reader = TV2C637_read_dead;
    }

    int value = TV2C637_invoke(&dispatch);
    dfb_sink_int(value);
}


namespace {
struct TV2C638_Cell {
    int live;
    int noise;
};

typedef void (*TV2C638_Callback)(TV2C638_Cell*);

TV2_NOINLINE void TV2C638_write_live(TV2C638_Cell* cell) {
    cell->live = dfb_source_A();
}

TV2_NOINLINE void TV2C638_write_noise(TV2C638_Cell* cell) {
    cell->noise = dfb_source_B();
}

TV2_NOINLINE TV2C638_Callback TV2C638_pick(int selector) {
    static TV2C638_Callback table[2] = { TV2C638_write_noise, TV2C638_write_live };
    return table[(selector ^ 0x31) & 1];
}
}

extern "C" TV2_NOINLINE void case_TV2C638_computed_callback_field_summary(void) {
    TV2C638_Cell cell = { 0, 0 };
    TV2C638_Callback cb = TV2C638_pick(0x30);
    cb(&cell);
    TV2C638_write_noise(&cell);
    dfb_sink_int(cell.live);
}


struct TV2C639Node {
    int hot;
    int cold;
    int pad;
};

TV2_NOINLINE static void tv2c639_store_lane(TV2C639Node* n, int v) {
    n->hot = v;
}

TV2_NOINLINE static int tv2c639_select_lane(TV2C639Node* first, TV2C639Node* second, int selector) {
    TV2C639Node* chosen = (selector & 1) ? second : first;
    return chosen->hot;
}

extern "C" TV2_NOINLINE void case_TV2C639_alias_join_field_kill(void) {
    TV2C639Node left = {0, 0, 0};
    TV2C639Node right = {0, 0, 0};
    int a = dfb_source_A();
    int b = dfb_source_B();
    int c = dfb_source_C();

    tv2c639_store_lane(&left, a);
    tv2c639_store_lane(&right, b);
    left.cold = c;
    right.cold = c + 17;
    left.hot = 0x5a5a;

    int out = tv2c639_select_lane(&left, &right, 1);
    dfb_sink_int(out);
}


struct TV2C640_Node {
    int live;
    int noise;
};

struct TV2C640_Base {
    virtual ~TV2C640_Base() {}
    virtual int pick(TV2C640_Node* n) = 0;
};

struct TV2C640_ReadLive : TV2C640_Base {
    int pick(TV2C640_Node* n) override {
        return n->live;
    }
};

typedef void (*TV2C640_Callback)(TV2C640_Node*, int, int);

static TV2_NOINLINE void TV2C640_write_live_noise(TV2C640_Node* n, int live, int noise) {
    n->noise = noise;
    n->live = live;
}

extern "C" TV2_NOINLINE void case_TV2C640_lambda_virtual_heap_field_kill() {
    TV2C640_Node* n = new TV2C640_Node{0, 0};
    int a = dfb_source_A();
    int b = dfb_source_B();
    int c = dfb_source_C();
    TV2C640_Callback cb = TV2C640_write_live_noise;
    auto stage = [cb, n](int live, int noise) {
        cb(n, live, noise);
        n->noise = noise ^ 0x1234;
    };
    stage(a, b);
    n->noise = c;
    TV2C640_Base* reader = new TV2C640_ReadLive();
    int out = reader->pick(n);
    dfb_sink_int(out);
    delete reader;
    delete n;
}


struct TV2C641_Cell {
    int lane0;
    int lane1;
    int noise;
};

static TV2_NOINLINE void tv2c641_write_lane(TV2C641_Cell* cell, int choose_a) {
    int a = dfb_source_A();
    int b = dfb_source_B();
    cell->noise = b ^ 0x5a5a;
    if ((choose_a ^ 0x13) == 0x12) {
        cell->lane0 = a + 9;
    } else {
        cell->lane0 = b + 11;
    }
    cell->lane1 = b - 3;
}

extern "C" TV2_NOINLINE void case_TV2C641_stack_field_kill_after_branch(void) {
    TV2C641_Cell cell = {0, 0, 0};
    tv2c641_write_lane(&cell, 1);
    cell.lane1 = 0x314159;
    dfb_sink_int(cell.lane0);
}


struct TV2C642_Node {
  int left;
  int pad;
  int right;
};

static TV2_NOINLINE int TV2C642_pick_right(TV2C642_Node* n, int noise) {
  volatile int guard = (noise ^ 0x13579) & 3;
  if (guard == 99) {
    return n->left;
  }
  return n->right;
}

extern "C" TV2_NOINLINE void case_TV2C642_field_overwrite_helper_noise(void) {
  TV2C642_Node node;
  node.left = dfb_source_B();
  node.pad = dfb_source_C();
  node.right = dfb_source_A();
  node.left = 0x6420;
  int out = TV2C642_pick_right(&node, node.pad);
  dfb_sink_int(out);
}


struct TV2C643_Cell {
    int payload;
    int decoy;
};

typedef void (*TV2C643_WriteFn)(TV2C643_Cell *, int);

TV2_NOINLINE static void tv2c643_write_payload(TV2C643_Cell *cell, int v) {
    cell->payload = v;
}

TV2_NOINLINE static void tv2c643_write_decoy(TV2C643_Cell *cell, int v) {
    cell->decoy = v;
}

TV2_NOINLINE static int tv2c643_read_payload(const TV2C643_Cell *cell) {
    return cell->payload;
}

extern "C" TV2_NOINLINE void case_TV2C643_indirect_field_write_then_decoy_overwrite(void) {
    TV2C643_Cell cell;
    cell.payload = 0x11111111;
    cell.decoy = dfb_source_B();
    TV2C643_WriteFn writer = tv2c643_write_payload;
    writer(&cell, dfb_source_A());
    tv2c643_write_decoy(&cell, 0x22222222);
    dfb_sink_int(tv2c643_read_payload(&cell));
}


struct TV2C644_Row {
    int live;
    int dead;
};

typedef void (*TV2C644_WriteFn)(TV2C644_Row *, int);

static TV2_NOINLINE void tv2c644_write_live(TV2C644_Row *row, int v) {
    row->live = v;
}

static TV2_NOINLINE void tv2c644_write_dead(TV2C644_Row *row, int v) {
    row->dead = v;
}

extern "C" TV2_NOINLINE void case_TV2C644_callback_field_lane_survives_dead_write() {
    TV2C644_Row row = {0, 0};
    int a = dfb_source_A();
    int b = dfb_source_B();
    int c = dfb_source_C();
    TV2C644_WriteFn write = ((a ^ 0x55) != 0) ? tv2c644_write_live : tv2c644_write_live;
    write(&row, a);
    tv2c644_write_dead(&row, b);
    int noise = c ^ row.dead;
    row.dead = noise;
    dfb_sink_int(row.live);
}


struct TV2C645_Cell { int lane0; int lane1; int noise; };

TV2_NOINLINE static void tv2c645_store_first_lane(TV2C645_Cell* c, int v) {
    c->lane0 = v;
}

TV2_NOINLINE static void tv2c645_store_second_lane(TV2C645_Cell* c, int v) {
    c->lane1 = v;
}

TV2_NOINLINE static int tv2c645_pick_live_lane(TV2C645_Cell* c, int selector) {
    int* p = selector ? &c->lane1 : &c->lane0;
    return *p;
}

extern "C" TV2_NOINLINE void case_TV2C645_split_store_indirect_lane(void) {
    TV2C645_Cell c = {0, 0, 0};
    int a = dfb_source_A();
    int b = dfb_source_B();
    int distract = dfb_source_C();
    tv2c645_store_first_lane(&c, a);
    tv2c645_store_second_lane(&c, b);
    c.noise = distract;
    int out = tv2c645_pick_live_lane(&c, 1);
    dfb_sink_int(out);
}


struct TV2C646_Cell {
    int live;
    int dead;
};

TV2_NOINLINE static int tv2c646_affine_keep(int v) {
    return (v * 3) + 17;
}

TV2_NOINLINE static void tv2c646_store_live(TV2C646_Cell* cell, int live_value, int noise_value) {
    cell->dead = noise_value;
    cell->live = live_value;
}

extern "C" TV2_NOINLINE void case_TV2C646_heap_lambda_alias_overwrite(void) {
    int a = dfb_source_A();
    int b = dfb_source_B();

    TV2C646_Cell* cell = new TV2C646_Cell();
    cell->live = b;
    cell->dead = a;

    auto writer = [cell](int live_value, int noise_value) {
        tv2c646_store_live(cell, live_value, noise_value);
    };

    writer(tv2c646_affine_keep(a), b);
    int out = cell->live + 5;
    dfb_sink_int(out);
    delete cell;
}


struct TV2C647_Cell {
  int live;
  int dead;
};

typedef void (*TV2C647_WriteFn)(TV2C647_Cell *, int, int);

static TV2_NOINLINE void tv2c647_write_pair(TV2C647_Cell *cell, int first, int second) {
  int TV2C647_Cell::* slot = &TV2C647_Cell::live;
  cell->dead = first;
  cell->*slot = first;
  cell->*slot = second;
}

extern "C" TV2_NOINLINE void case_TV2C647_member_pointer_callback_overwrite(void) {
  TV2C647_Cell cell = {0, 0};
  int a = dfb_source_A();
  int b = dfb_source_B();
  TV2C647_WriteFn writer = tv2c647_write_pair;
  writer(&cell, a, b);
  dfb_sink_int(cell.live);
}


struct TV2C648_Node {
    int lane0;
    int lane1;
    int lane2;
};

static TV2_NOINLINE void tv2c648_write_lane(TV2C648_Node* n, int selector, int value) {
    volatile int guard = selector ^ 0x4a17;
    if ((guard & 1) == 0) {
        n->lane1 = value;
    } else {
        n->lane0 = dfb_source_C();
        n->lane1 = value;
    }
}

extern "C" TV2_NOINLINE void case_TV2C648_indirect_field_overwrite_sink(void) {
    TV2C648_Node n;
    n.lane0 = dfb_source_B();
    n.lane1 = dfb_source_A();
    n.lane2 = 0x6480;
    tv2c648_write_lane(&n, 0x4a16, 0x13572468);
    dfb_sink_int(n.lane1);
}


struct TV2C649_Cell {
    int live;
    int noise;
};

struct TV2C649_Base {
    virtual ~TV2C649_Base() {}
    virtual int pick(TV2C649_Cell *cell) = 0;
};

struct TV2C649_First : TV2C649_Base {
    int pick(TV2C649_Cell *cell) override {
        cell->noise = dfb_source_B();
        cell->live = 0x6490;
        return cell->noise;
    }
};

struct TV2C649_Second : TV2C649_Base {
    int pick(TV2C649_Cell *cell) override {
        cell->noise = 0x6491;
        cell->live = dfb_source_A();
        return cell->live;
    }
};

extern "C" TV2_NOINLINE void case_TV2C649_virtual_field_overwrite_precise(void) {
    TV2C649_Cell cell;
    cell.live = dfb_source_C();
    cell.noise = 0x6492;

    TV2C649_First first;
    TV2C649_Second second;
    TV2C649_Base *base = &second;
    int chosen = base->pick(&cell);

    if ((chosen & 1) == (cell.live & 1)) {
        dfb_sink_int(cell.live);
    } else {
        dfb_sink_int(cell.live);
    }
}


struct TV2C650Node {
    int tag;
    int payload;
    int decoy;
};

static TV2_NOINLINE void tv2c650_store_selected_lane(TV2C650Node *node, int value, int selector) {
    if (((selector ^ 0x1357) & 1) == 0) {
        node->payload = value;
    } else {
        node->decoy = value;
    }
}

static TV2_NOINLINE int tv2c650_read_payload_after_noise(TV2C650Node *node) {
    node->tag ^= 0x55;
    node->decoy = 0x70707070;
    return node->payload;
}

extern "C" TV2_NOINLINE void case_TV2C650_struct_lane_store_through_helper(void) {
    TV2C650Node node = {0, 0, 0};
    int live = dfb_source_A();
    int dead = dfb_source_B();
    tv2c650_store_selected_lane(&node, live, 0x1357);
    node.decoy = dead;
    int out = tv2c650_read_payload_after_noise(&node);
    dfb_sink_int(out);
}


struct TV2C651_Cell { int live; int decoy; };

static TV2_NOINLINE void tv2c651_store_live(TV2C651_Cell* cell, int value) {
    cell->live = value;
}

static TV2_NOINLINE void tv2c651_store_decoy(TV2C651_Cell* cell, int value) {
    cell->decoy = value;
}

static TV2_NOINLINE int tv2c651_read_live(const TV2C651_Cell* cell) {
    return cell->live;
}

extern "C" TV2_NOINLINE void case_TV2C651_field_rewrite_live_decoy_precision() {
    TV2C651_Cell cell;
    cell.live = 0x1357;
    cell.decoy = 0x2468;
    tv2c651_store_decoy(&cell, dfb_source_B());
    tv2c651_store_live(&cell, dfb_source_A());
    tv2c651_store_decoy(&cell, 0x55aa);
    int out = tv2c651_read_live(&cell);
    dfb_sink_int(out);
}


struct TV2C652_Cell {
    int lanes[3];
};

TV2_NOINLINE static void tv2c652_store_lane(TV2C652_Cell* cell, int index, int value) {
    cell->lanes[index] = value;
}

TV2_NOINLINE static int tv2c652_read_lane(const TV2C652_Cell* cell, int index) {
    return cell->lanes[index];
}

extern "C" TV2_NOINLINE void case_TV2C652_indirect_indexed_lane_overwrite(void) {
    TV2C652_Cell cell{};
    int a = dfb_source_A();
    int b = dfb_source_B();
    int c = dfb_source_C();

    volatile int guard = 7;
    int live_index = (guard & 1) + 1;
    int dead_index = live_index - 1;

    tv2c652_store_lane(&cell, live_index, a);
    tv2c652_store_lane(&cell, dead_index, b);
    tv2c652_store_lane(&cell, live_index, c);

    int out = tv2c652_read_lane(&cell, live_index);
    dfb_sink_int(out);
}


struct TV2C653_Box {
    unsigned int lane;
    unsigned int noise;
};

extern "C" TV2_NOINLINE void case_TV2C653_partial_store_kills_sink_lane() {
    TV2C653_Box box = {0u, 0u};
    unsigned int tainted = (unsigned int)dfb_source_A();
    unsigned int distractor = (unsigned int)dfb_source_B();
    box.lane = tainted ^ 0x55aa33ccu;
    unsigned short *low = (unsigned short *)&box.lane;
    *low = 0x1234u;
    box.noise = distractor;
    unsigned int observed = (unsigned int)(*low);
    dfb_sink_int((int)observed);
}


struct TV2C654_Cell {
    int lane0;
    int lane1;
    int noise;
};

static TV2_NOINLINE void tv2c654_store_selected_lane(TV2C654_Cell *cell, int live, int dead) {
    cell->lane0 = dead;
    cell->lane1 = live;
    cell->noise = dead ^ 0x55aa55aa;
}

extern "C" TV2_NOINLINE void case_TV2C654_field_lane_after_overwrite(void) {
    TV2C654_Cell cell;
    int a = dfb_source_A();
    int b = dfb_source_B();
    tv2c654_store_selected_lane(&cell, a, b);
    cell.lane0 = 0x6540;
    int out = cell.lane1 + 7;
    dfb_sink_int(out);
}


struct TV2C655_Cell {
    int lanes[4];
};

static TV2_NOINLINE void TV2C655_write_cell(TV2C655_Cell* cell, int slot, int value) {
    cell->lanes[slot & 3] = value;
}

extern "C" TV2_NOINLINE void case_TV2C655_masked_slot_store_reload(void) {
    TV2C655_Cell cell = {{0, 0, 0, 0}};
    int a = dfb_source_A();
    int b = dfb_source_B();
    int c = dfb_source_C();
    TV2C655_write_cell(&cell, 0, b);
    TV2C655_write_cell(&cell, 1, a);
    TV2C655_write_cell(&cell, 2, c);
    TV2C655_write_cell(&cell, 3, b ^ c);
    int selected = cell.lanes[(a ^ a) + 1];
    dfb_sink_int(selected);
}


struct TV2C656Lane {
    int value;
    int noise;
};

extern "C" TV2_NOINLINE void case_TV2C656_masked_index_store_then_struct_copy(void) {
    TV2C656Lane lanes[3] = {};
    int a = dfb_source_A();
    int b = dfb_source_B();
    int c = dfb_source_C();
    unsigned selector = ((unsigned)(a ^ b) & 2u) >> 1;
    selector = selector ^ selector;
    lanes[0].value = b;
    lanes[0].noise = c;
    lanes[selector].value = a;
    TV2C656Lane chosen = lanes[0];
    dfb_sink_int(chosen.value);
}


struct TV2C657_Cell {
    int lane[2];
    int guard;
};

static TV2_NOINLINE int TV2C657_pick_one(void) {
    volatile int one = 1;
    return one & 1;
}

extern "C" TV2_NOINLINE void case_TV2C657_masked_alias_copy_kill() {
    TV2C657_Cell cell = {{0, 0}, 0};
    TV2C657_Cell* p = &cell;
    int idx = TV2C657_pick_one();

    int decoy_b = dfb_source_B();
    int live_a = dfb_source_A();
    p->lane[idx ^ 1] = decoy_b;
    p->lane[idx] = live_a;

    TV2C657_Cell mirror = *p;
    mirror.lane[idx ^ 1] = dfb_source_C();
    mirror.guard = decoy_b ^ 0x657;

    int out = mirror.lane[idx];
    dfb_sink_int(out);
}


struct TV2C658_Cell {
    int lane0;
    int lane1;
    int noise;
};

static TV2_NOINLINE TV2C658_Cell case_TV2C658_make_cell(int live, int decoy, int noise) {
    TV2C658_Cell c;
    c.lane0 = decoy;
    c.lane1 = live;
    c.noise = noise;
    return c;
}

extern "C" TV2_NOINLINE void case_TV2C658_struct_return_lane_rewrite(void) {
    int live = dfb_source_A();
    int decoy = dfb_source_B();
    int noise = dfb_source_C();
    TV2C658_Cell c = case_TV2C658_make_cell(live, decoy, noise);
    c.lane0 = 0x13579;
    c.noise = c.lane0 ^ 0x2468;
    int out = c.lane1;
    dfb_sink_int(out);
}


struct TV2C659_Cell {
    int payload;
    int noise;
};

extern "C" TV2_NOINLINE void case_TV2C659_bytewise_payload_copy_kills_decoys() {
    TV2C659_Cell cells[2] = {};

    volatile int *decoy_slot = &cells[1].payload;
    *decoy_slot = dfb_source_B();
    cells[0].payload = dfb_source_A();
    cells[0].noise = dfb_source_C();

    unsigned char *dst = reinterpret_cast<unsigned char *>(&cells[1].payload);
    unsigned char *src = reinterpret_cast<unsigned char *>(&cells[0].payload);
    for (unsigned i = 0; i < sizeof(int); ++i) {
        dst[i] = src[i];
    }

    dfb_sink_int(cells[1].payload);
}


struct TV2C660_Cell {
    int live;
    int decoy;
};

static TV2_NOINLINE TV2C660_Cell TV2C660_make_cell(int live, int decoy) {
    TV2C660_Cell c;
    c.live = live;
    c.decoy = decoy;
    return c;
}

static TV2_NOINLINE void TV2C660_store_selected(TV2C660_Cell* cells, int idx, int value) {
    cells[idx].live = value;
}

extern "C" TV2_NOINLINE void case_TV2C660_copy_then_selected_field_overwrite(void) {
    TV2C660_Cell cells[2];
    cells[0] = TV2C660_make_cell(dfb_source_B(), dfb_source_C());
    cells[1] = TV2C660_make_cell(dfb_source_C(), dfb_source_B());

    TV2C660_Cell copied = cells[0];
    cells[1] = copied;
    TV2C660_store_selected(cells, 1, dfb_source_A());

    int observed = cells[1].live;
    dfb_sink_int(observed);
}


struct TV2C661_Cell {
    int lane0;
    int lane1;
    int noise;
};

TV2_NOINLINE static void tv2c661_store_slot(TV2C661_Cell* cells, int selector, int live, int decoy) {
    int idx = (selector ^ 0x35) & 1;
    cells[idx].lane0 = decoy;
    cells[idx].lane1 = live;
    cells[idx ^ 1].lane1 = dfb_source_C();
}

extern "C" TV2_NOINLINE void case_TV2C661_masked_slot_copy_live_lane(void) {
    TV2C661_Cell cells[2] = {};
    int a = dfb_source_A();
    int b = dfb_source_B();
    tv2c661_store_slot(cells, 0x34, a, b);
    TV2C661_Cell copy = cells[1];
    copy.lane0 = 0x6610;
    int out = copy.lane1;
    dfb_sink_int(out);
}


struct TV2C662_Cell {
  unsigned short low;
  unsigned short high;
};

struct TV2C662_Box {
  TV2C662_Cell cell;
  unsigned int guard;
};

static TV2_NOINLINE void tv2c662_copy_bytes(void* dst, const void* src, unsigned long n) {
  unsigned char* d = (unsigned char*)dst;
  const unsigned char* s = (const unsigned char*)src;
  for (unsigned long i = 0; i < n; ++i) {
    d[i] = s[i];
  }
}

extern "C" TV2_NOINLINE void case_TV2C662_memcpy_low_field_survives_adjacent_noise() {
  TV2C662_Box src = {};
  src.cell.low = (unsigned short)dfb_source_A();
  src.cell.high = (unsigned short)dfb_source_B();
  src.guard = (unsigned int)dfb_source_C();

  unsigned char raw[sizeof(TV2C662_Box)] = {};
  TV2C662_Box dst = {};
  tv2c662_copy_bytes(raw, &src, (unsigned long)sizeof(src));
  tv2c662_copy_bytes(&dst, raw, (unsigned long)sizeof(dst));

  dfb_sink_int((int)dst.cell.low);
}


struct TV2C663_Cell { int lane0; int lane1; int noise; };

extern "C" TV2_NOINLINE void case_TV2C663_masked_store_reload_precise(void) {
    TV2C663_Cell cells[3] = {};
    int a = dfb_source_A();
    int b = dfb_source_B();
    int c = dfb_source_C();
    int idx = (a ^ a) + 1;
    cells[0].lane0 = b;
    cells[1].lane0 = c;
    cells[idx].lane0 = a;
    cells[idx].lane1 = 0x6631;
    cells[2].lane0 = b ^ c;
    int out = cells[idx].lane0;
    dfb_sink_int(out);
}


struct TV2C664_Pair {
  int left;
  int right;
};

static TV2_NOINLINE void tv2c664_write_left(TV2C664_Pair* p, int v) {
  p->left = v;
}

static TV2_NOINLINE void tv2c664_write_right(TV2C664_Pair* p, int v) {
  p->right = v;
}

extern "C" TV2_NOINLINE void case_TV2C664_multi_sink_alias_field_split() {
  TV2C664_Pair cell = {0, 0};
  int a = dfb_source_A();
  int b = dfb_source_B();
  int c = dfb_source_C();
  TV2C664_Pair* alias = &cell;
  tv2c664_write_left(alias, a);
  tv2c664_write_right(&cell, c);
  tv2c664_write_right(alias, b);
  dfb_sink_int(cell.left);
  dfb_sink_int(alias->right);
}


static int tv2c665_slot;
static int tv2c665_shadow;

static TV2_NOINLINE void tv2c665_store_slot(int v) {
  tv2c665_slot = v;
}

static TV2_NOINLINE void tv2c665_store_shadow(int v) {
  tv2c665_shadow = v;
}

extern "C" TV2_NOINLINE void case_TV2C665_static_overwrite_no_source() {
  int a = dfb_source_A();
  int b = dfb_source_B();
  tv2c665_store_slot(a);
  tv2c665_store_shadow(b);
  tv2c665_store_slot(0x6650);
  int out = tv2c665_slot;
  dfb_sink_int(out);
}


struct TV2C666_Cell {
    int left;
    int right;
    int noise;
};

TV2_NOINLINE void TV2C666_stage_store(TV2C666_Cell* cell) {
    cell->left = dfb_source_A();
    cell->right = dfb_source_B();
    cell->noise = dfb_source_C();
}

TV2_NOINLINE void TV2C666_stage_kill_and_distract(TV2C666_Cell* live, TV2C666_Cell* stale) {
    live->noise = 0x6660;
    stale->left = dfb_source_C();
}

extern "C" TV2_NOINLINE void case_TV2C666_multi_sink_stale_copy_kill(void) {
    TV2C666_Cell cell = {0, 0, 0};
    TV2C666_stage_store(&cell);
    TV2C666_Cell stale = cell;
    TV2C666_stage_kill_and_distract(&cell, &stale);
    int* first = &cell.left;
    int* second = &cell.right;
    dfb_sink_int(*first);
    dfb_sink_int(*second);
}


struct TV2C667_Cell {
    int live;
    int stale;
    int shadow;
};

static TV2_NOINLINE void tv2c667_write_live(TV2C667_Cell* cell, int value) {
    cell->live = value;
}

static TV2_NOINLINE void tv2c667_write_stale(TV2C667_Cell* cell, int value) {
    cell->stale = value;
}

static TV2_NOINLINE int tv2c667_read_selected(TV2C667_Cell* cell, int which) {
    return which ? cell->live : cell->shadow;
}

extern "C" TV2_NOINLINE void case_TV2C667_multi_sink_field_alias_reload(void) {
    TV2C667_Cell cell = {0, 0, 0};
    TV2C667_Cell* alias = &cell;
    int a = dfb_source_A();
    int b = dfb_source_B();
    int c = dfb_source_C();
    tv2c667_write_stale(alias, b);
    alias->shadow = c;
    tv2c667_write_live(&cell, a);
    alias->stale = 0x6670;
    dfb_sink_int(tv2c667_read_selected(alias, 1));
    dfb_sink_int(alias->shadow);
}


struct TV2C668_Cell {
    int live;
    int decoy;
};

static TV2_NOINLINE void tv2c668_write_live(TV2C668_Cell* cell) {
    cell->live = dfb_source_A();
}

static TV2_NOINLINE void tv2c668_write_decoy(TV2C668_Cell* cell) {
    cell->decoy = dfb_source_B();
}

static TV2_NOINLINE void tv2c668_kill_decoy(TV2C668_Cell* cell) {
    cell->decoy = 0x6680;
}

extern "C" TV2_NOINLINE void case_TV2C668_multi_sink_field_alias_kill() {
    TV2C668_Cell first{0, 0};
    TV2C668_Cell second{0, 0};
    TV2C668_Cell* picked = &second;
    tv2c668_write_decoy(&first);
    tv2c668_write_live(picked);
    tv2c668_write_decoy(picked);
    tv2c668_kill_decoy(picked);
    dfb_sink_int(first.decoy);
    dfb_sink_int(picked->live);
}


struct TV2C669_Packed {
    unsigned char lanes[4];
};

static TV2_NOINLINE void tv2c669_store_low_byte(TV2C669_Packed* p) {
    int a = dfb_source_A();
    p->lanes[1] = static_cast<unsigned char>(a);
}

static TV2_NOINLINE void tv2c669_store_killed_neighbor(TV2C669_Packed* p) {
    int b = dfb_source_B();
    p->lanes[2] = static_cast<unsigned char>(b);
    p->lanes[2] = 0x2a;
}

extern "C" TV2_NOINLINE void case_TV2C669_byte_lane_neighbor_kill() {
    TV2C669_Packed p{{0, 0, 0, 0}};
    tv2c669_store_low_byte(&p);
    tv2c669_store_killed_neighbor(&p);
    int out = static_cast<int>(p.lanes[1]);
    dfb_sink_int(out);
}


struct TV2C670_Cell {
  int live;
  int shadow;
  int spare;
};

TV2_NOINLINE void tv2c670_write_live(TV2C670_Cell* cell) {
  cell->live = dfb_source_A();
}

TV2_NOINLINE void tv2c670_write_shadow_then_kill(TV2C670_Cell* cell) {
  cell->shadow = dfb_source_B();
  cell->shadow = 0x6700;
}

TV2_NOINLINE void case_TV2C670_multi_sink_alias_field_kill() {
  TV2C670_Cell cell = {0, 0, 0};
  TV2C670_Cell* alias = &cell;
  tv2c670_write_live(alias);
  tv2c670_write_shadow_then_kill(&cell);
  alias->spare = dfb_source_C();
  dfb_sink_int(cell.live);
  dfb_sink_int(alias->shadow);
}


struct TV2C671_Packed {
    unsigned char tag;
    unsigned char live0;
    unsigned char live1;
    unsigned char pad;
    int tail;
};

static TV2_NOINLINE void tv2c671_write_bytes(TV2C671_Packed* p) {
    int a = dfb_source_A();
    int b = dfb_source_B();
    int c = dfb_source_C();
    p->live0 = (unsigned char)(a & 0xff);
    p->live1 = (unsigned char)(b & 0xff);
    p->tail = c;
    p->live0 = 0x35;
}

extern "C" TV2_NOINLINE void case_TV2C671_packed_byte_overwrite_multisink() {
    TV2C671_Packed cell = {0, 0, 0, 0, 0};
    tv2c671_write_bytes(&cell);
    dfb_sink_int((int)cell.live0);
    dfb_sink_int((int)cell.live1);
    dfb_sink_int(cell.tail);
}


struct TV2C672_Cell {
    int live;
    int decoy;
};

static TV2_NOINLINE void tv2c672_write_pair(TV2C672_Cell* first, TV2C672_Cell* second) {
    first->live = dfb_source_A();
    first->decoy = dfb_source_B();
    second->live = dfb_source_C();
    second->decoy = first->decoy;
    first->live = 0x6720;
}

extern "C" TV2_NOINLINE void case_TV2C672_multi_sink_alias_overwrite(void) {
    TV2C672_Cell cells[2] = {};
    tv2c672_write_pair(&cells[0], &cells[1]);
    dfb_sink_int(cells[0].decoy);
    dfb_sink_int(cells[1].live);
}


struct TV2C673_Cell {
    int live;
    int decoy;
};

TV2_NOINLINE static void tv2c673_write_live(TV2C673_Cell* cell) {
    cell->live = dfb_source_A();
}

TV2_NOINLINE static void tv2c673_write_decoy(TV2C673_Cell* cell) {
    cell->decoy = dfb_source_B();
}

TV2_NOINLINE static int tv2c673_read_live(const TV2C673_Cell* cell) {
    return cell->live;
}

TV2_NOINLINE static int tv2c673_read_decoy(const TV2C673_Cell* cell) {
    return cell->decoy;
}

extern "C" TV2_NOINLINE void case_TV2C673_multi_sink_field_alias_split() {
    TV2C673_Cell cell = {0, 0};
    tv2c673_write_live(&cell);
    tv2c673_write_decoy(&cell);
    int first = tv2c673_read_live(&cell);
    int second = tv2c673_read_decoy(&cell);
    dfb_sink_int(first);
    dfb_sink_int(second);
}


struct TV2C674_Packed {
    unsigned char lo;
    unsigned char mid;
    unsigned short hi;
};

TV2_NOINLINE static void tv2c674_store_bytes(TV2C674_Packed* p) {
    int a = dfb_source_A();
    int b = dfb_source_B();
    p->lo = (unsigned char)(a & 0xff);
    p->mid = (unsigned char)(b & 0xff);
    p->hi = 0x4444u;
}

TV2_NOINLINE static int tv2c674_read_mid(const TV2C674_Packed* p) {
    return (int)p->mid;
}

extern "C" TV2_NOINLINE void case_TV2C674_byte_subrange_selected_reload() {
    TV2C674_Packed p = {0, 0, 0};
    tv2c674_store_bytes(&p);
    int selected = tv2c674_read_mid(&p);
    dfb_sink_int(selected);
}


struct TV2C675_Cell {
    int live;
    int stale;
};

TV2_NOINLINE static void tv2c675_store_payload(TV2C675_Cell* cell) {
    cell->live = dfb_source_A();
    cell->stale = dfb_source_B();
}

TV2_NOINLINE static void tv2c675_kill_stale(TV2C675_Cell* cell) {
    cell->stale = 0x6750;
}

extern "C" TV2_NOINLINE void case_TV2C675_multi_sink_field_overwrite(void) {
    TV2C675_Cell first{0, 0};
    TV2C675_Cell copy{0, 0};
    tv2c675_store_payload(&first);
    copy = first;
    tv2c675_kill_stale(&copy);
    int decoy = dfb_source_C();
    dfb_sink_int(copy.live);
    dfb_sink_int(copy.stale + (decoy & 0));
}


struct FusionPartialCopyCell {
    int live;
    int decoy;
};

typedef void (*FusionPartialCopyWriter)(FusionPartialCopyCell*);

static TV2_NOINLINE void fusion_partial_copy_seed_a(FusionPartialCopyCell* cell) {
    cell->live = dfb_source_A();
    cell->decoy = dfb_source_C();
}

static TV2_NOINLINE void fusion_partial_copy_seed_b(FusionPartialCopyCell* cell) {
    cell->live = dfb_source_A() ^ 0x13579BDF;
    cell->decoy = dfb_source_C() ^ 0x2468ACE0;
}

static TV2_NOINLINE void fusion_partial_copy_patch_byte(FusionPartialCopyCell* cell) {
    unsigned char* live_bytes = reinterpret_cast<unsigned char*>(&cell->live);
    live_bytes[0] = static_cast<unsigned char>(dfb_source_B());
}

static TV2_NOINLINE void fusion_partial_copy_object(FusionPartialCopyCell* dst, const FusionPartialCopyCell* src) {
    unsigned char* dst_bytes = reinterpret_cast<unsigned char*>(dst);
    const unsigned char* src_bytes = reinterpret_cast<const unsigned char*>(src);
    for (unsigned int i = 0; i < sizeof(FusionPartialCopyCell); ++i) {
        dst_bytes[i] = src_bytes[i];
    }
}

extern "C" TV2_NOINLINE void case_TV2C676_callback_partial_copy_precision() {
    static_assert(sizeof(int) >= 2, "partial-byte fusion requires at least two-byte int");
    FusionPartialCopyCell staged = {};
    FusionPartialCopyCell copied = {};
    FusionPartialCopyWriter writers[2] = {
        &fusion_partial_copy_seed_a,
        &fusion_partial_copy_seed_b
    };
    volatile unsigned int selected = 0u;
    writers[selected & 1u](&staged);
    fusion_partial_copy_patch_byte(&staged);
    fusion_partial_copy_object(&copied, &staged);
    dfb_sink_int(copied.live);
}


struct TV2C677_Cell {
    int Payload;
    int Decoy;
};

TV2_NOINLINE static void TV2C677_copy_cell(TV2C677_Cell* Dst, const TV2C677_Cell* Src) {
    *Dst = *Src;
}

TV2_NOINLINE static void TV2C677_store_selected(int* Field, int Value) {
    *Field = Value;
}

extern "C" TV2_NOINLINE void case_TV2C677_callback_exact_field_overwrite_after_copy() {
    TV2C677_Cell Seed = { dfb_source_A(), dfb_source_B() };
    TV2C677_Cell Live = { 0, 0 };
    TV2C677_copy_cell(&Live, &Seed);

    int* SelectedField = &Live.Payload;
    void (*volatile Writer)(int*, int) = &TV2C677_store_selected;
    const int Replacement = dfb_source_C();
    Writer(SelectedField, Replacement);

    dfb_sink_int(Live.Payload);
}


struct TV2C678_Lane {
    unsigned short low;
    unsigned short high;
};

struct TV2C678_Cell {
    TV2C678_Lane payload;
    unsigned int neighbor;
};

using TV2C678_Callback = void (*)(volatile TV2C678_Lane*);

static TV2_NOINLINE void TV2C678_write_sources(volatile TV2C678_Lane* lane) {
    lane->low = static_cast<unsigned short>(dfb_source_A());
    lane->high = static_cast<unsigned short>(dfb_source_B());
}

static TV2_NOINLINE void TV2C678_copy_cell(const TV2C678_Cell* src, TV2C678_Cell* dst) {
    dst->payload = src->payload;
    dst->neighbor = src->neighbor;
}

extern "C" TV2_NOINLINE void case_TV2C678_callback_partial_kill_copy_negative() {
    TV2C678_Cell cell{};
    TV2C678_Callback volatile callback = &TV2C678_write_sources;
    callback(&cell.payload);

    volatile unsigned int* neighbor_alias = &cell.neighbor;
    *neighbor_alias = static_cast<unsigned int>(dfb_source_C());

    volatile TV2C678_Lane* payload_alias = &cell.payload;
    payload_alias->low = 0x1357u;
    payload_alias->high = 0x2468u;

    TV2C678_Cell snapshot{};
    TV2C678_copy_cell(&cell, &snapshot);
    const unsigned int value =
        (static_cast<unsigned int>(snapshot.payload.high) << 16) |
        static_cast<unsigned int>(snapshot.payload.low);
    dfb_sink_int(static_cast<int>(value));
}


struct TV2C679_Words {
    uint16_t lo;
    uint16_t hi;
};

struct TV2C679_Cell {
    TV2C679_Words payload;
    uint32_t noise;
};

TV2_NOINLINE static void TV2C679_fill_cell(TV2C679_Cell* out) {
    const uint32_t a = static_cast<uint32_t>(dfb_source_A());
    TV2C679_Cell tmp{};
    tmp.payload.lo = static_cast<uint16_t>(a);
    tmp.payload.hi = static_cast<uint16_t>(a >> 16);
    tmp.noise = static_cast<uint32_t>(dfb_source_B());
    *out = tmp;
}

TV2_NOINLINE static void TV2C679_patch_low(TV2C679_Cell* cell) {
    uint16_t* lane = &cell->payload.lo;
    *lane = static_cast<uint16_t>(dfb_source_C());
}

extern "C" TV2_NOINLINE void case_TV2C679_partial_patch_after_copy_fusion() {
    TV2C679_Cell cell{};
    TV2C679_fill_cell(&cell);
    TV2C679_patch_low(&cell);
    const uint32_t joined = static_cast<uint32_t>(cell.payload.lo) |
        (static_cast<uint32_t>(cell.payload.hi) << 16);
    dfb_sink_int(static_cast<int>(joined));
}


struct TV2C680_Cell {
    unsigned int payload;
    unsigned int noise;
};

using TV2C680_Writer = void (*)(TV2C680_Cell*);

static TV2_NOINLINE void TV2C680_write_clean(TV2C680_Cell* cell) {
    cell->payload = 0x11223344u;
    cell->noise = 0x55667788u;
}

static TV2_NOINLINE void TV2C680_write_sources(TV2C680_Cell* cell) {
    cell->payload = static_cast<unsigned int>(dfb_source_C());
    cell->noise = static_cast<unsigned int>(dfb_source_B());
    cell->payload = static_cast<unsigned int>(dfb_source_A());
}

extern "C" TV2_NOINLINE void case_TV2C680_callback_partial_overwrite_copy() {
    TV2C680_Cell nodes[2] = {};
    TV2C680_Writer writers[2] = {TV2C680_write_clean, TV2C680_write_sources};
    volatile unsigned int selected = 1u;
    writers[selected & 1u](&nodes[1]);

    TV2C680_Cell* alias = (selected & 1u) ? &nodes[1] : &nodes[0];
    unsigned char* payload_bytes = reinterpret_cast<unsigned char*>(&alias->payload);
    payload_bytes[1] = 0x5au;

    TV2C680_Cell snapshot = *alias;
    dfb_sink_int(static_cast<int>(snapshot.payload));
}


struct TV2C681_Cell {
    int left;
    int right;
    int noise;
};

using TV2C681_Writer = void (*)(TV2C681_Cell*);

static TV2_NOINLINE void TV2C681_write_left(TV2C681_Cell* cell) {
    cell->left = dfb_source_A();
}

static TV2_NOINLINE void TV2C681_write_right(TV2C681_Cell* cell) {
    cell->right = dfb_source_B();
}

static TV2_NOINLINE void TV2C681_write_noise(TV2C681_Cell* cell) {
    cell->noise = dfb_source_C();
}

static TV2_NOINLINE void TV2C681_copy_cell(TV2C681_Cell* dst, const TV2C681_Cell* src) {
    *dst = *src;
}

static TV2_NOINLINE int TV2C681_pack_live(const TV2C681_Cell* cell) {
    return cell->left ^ cell->right;
}

extern "C" TV2_NOINLINE void case_TV2C681_callback_loop_snapshot_copy_overwrite(void) {
    TV2C681_Cell live = {0, 0, 0};
    TV2C681_Writer writers[3] = {
        &TV2C681_write_left,
        &TV2C681_write_noise,
        &TV2C681_write_right
    };

    for (unsigned int i = 0; i < 3; ++i) {
        writers[i](&live);
    }

    TV2C681_Cell snapshot = {0, 0, 0};
    TV2C681_copy_cell(&snapshot, &live);

    live.left = dfb_source_C();
    const int value = TV2C681_pack_live(&snapshot);
    dfb_sink_int(value);
}


struct TV2C682_Cell {
    int payload;
    int decoy;
};

using TV2C682_PatchFn = void (*)(TV2C682_Cell*, int);

TV2_NOINLINE static void TV2C682_seed(TV2C682_Cell* cell, int payload, int decoy) {
    cell->payload = payload;
    cell->decoy = decoy;
}

TV2_NOINLINE static void TV2C682_patch_12(TV2C682_Cell* cell, int value) {
    unsigned char* bytes = reinterpret_cast<unsigned char*>(&cell->payload);
    bytes[1] = static_cast<unsigned char>(value & 0xff);
    bytes[2] = static_cast<unsigned char>((value >> 8) & 0xff);
}

TV2_NOINLINE static void TV2C682_patch_21(TV2C682_Cell* cell, int value) {
    unsigned char* bytes = reinterpret_cast<unsigned char*>(&cell->payload);
    bytes[2] = static_cast<unsigned char>((value >> 8) & 0xff);
    bytes[1] = static_cast<unsigned char>(value & 0xff);
}

extern "C" TV2_NOINLINE void case_TV2C682_callback_partial_object_patch_after_copy_fusion() {
    static_assert(sizeof(int) == 4, "TV2C682 requires a four-byte int");
    TV2C682_Cell original{};
    TV2C682_seed(&original, dfb_source_A(), dfb_source_B());

    TV2C682_Cell copied = original;
    const int patch = dfb_source_C();
    volatile unsigned selector = 1u;
    TV2C682_PatchFn apply = (selector & 1u) ? TV2C682_patch_12 : TV2C682_patch_21;
    apply(&copied, patch);

    dfb_sink_int(copied.payload);
}


struct TV2C683_Cell {
    unsigned short low;
    unsigned short high;
    int decoy;
};

typedef void (*TV2C683_Writer)(TV2C683_Cell *, unsigned int);

TV2_NOINLINE static void TV2C683_write_high(TV2C683_Cell *cell, unsigned int value) {
    cell->high = static_cast<unsigned short>(value);
}

TV2_NOINLINE static void TV2C683_copy_cell(TV2C683_Cell *dst, const TV2C683_Cell *src) {
    unsigned char *out = reinterpret_cast<unsigned char *>(dst);
    const unsigned char *in = reinterpret_cast<const unsigned char *>(src);
    for (unsigned int i = 0; i < sizeof(TV2C683_Cell); ++i) {
        out[i] = in[i];
    }
}

extern "C" TV2_NOINLINE void case_TV2C683_callback_heap_partial_kill_copy_fusion() {
    static_assert(sizeof(unsigned short) == 2, "TV2C683 requires a 16-bit unsigned short");
    TV2C683_Cell *cells = new TV2C683_Cell[2]();
    const unsigned int source_a = static_cast<unsigned int>(dfb_source_A());
    const unsigned int source_b = static_cast<unsigned int>(dfb_source_B());
    const int source_c = dfb_source_C();

    cells[0].low = static_cast<unsigned short>(source_b);
    cells[0].decoy = source_c;
    TV2C683_Writer writer = &TV2C683_write_high;
    writer(&cells[0], source_a);

    cells[0].low = static_cast<unsigned short>(0x5a5aU);
    TV2C683_copy_cell(&cells[1], &cells[0]);

    const unsigned int value =
        (static_cast<unsigned int>(cells[1].high) << 16U) |
        static_cast<unsigned int>(cells[1].low);
    dfb_sink_int(static_cast<int>(value));
    delete[] cells;
}


struct TV2C684_Cell {
    int payload;
    int decoy;
};

static_assert(sizeof(int) == 4, "TV2C684 requires a four-byte int");

static TV2_NOINLINE void TV2C684_patch_two_bytes(unsigned char* field) {
    field[0] = 0x5a;
    field[1] = 0xa5;
}

static TV2_NOINLINE void TV2C684_copy_cell(TV2C684_Cell* dst, const TV2C684_Cell* src) {
    *dst = *src;
}

static TV2_NOINLINE int TV2C684_read_payload(const TV2C684_Cell* cell) {
    return cell->payload;
}

extern "C" TV2_NOINLINE void case_TV2C684_partial_callback_struct_copy() {
    TV2C684_Cell original;
    original.payload = dfb_source_A();
    original.decoy = dfb_source_B();

    void (*volatile patch)(unsigned char*) = &TV2C684_patch_two_bytes;
    patch(reinterpret_cast<unsigned char*>(&original.payload));

    TV2C684_Cell copied = {0, 0};
    TV2C684_copy_cell(&copied, &original);
    int value = TV2C684_read_payload(&copied);
    dfb_sink_int(value);
}


struct TV2C685_Cell {
    int payload;
    int decoy;
};

typedef void (*TV2C685_Writer)(TV2C685_Cell*);

static TV2_NOINLINE void TV2C685_write_overlay(TV2C685_Cell* out) {
    int a = dfb_source_A();
    int b = dfb_source_B();
    out->payload = a;
    out->decoy = dfb_source_C();

    unsigned char* dst = reinterpret_cast<unsigned char*>(&out->payload);
    const unsigned char* src = reinterpret_cast<const unsigned char*>(&b);
    dst[1] = src[1];
    dst[2] = src[2];
}

static TV2_NOINLINE void TV2C685_copy_cell(TV2C685_Cell* dst, const TV2C685_Cell* src) {
    *dst = *src;
}

extern "C" TV2_NOINLINE void case_TV2C685_callback_partial_overlay_copy() {
    static_assert(sizeof(int) == 4, "TV2C685 requires a four-byte int");
    TV2C685_Cell original = {};
    TV2C685_Cell copied = {};
    TV2C685_Writer volatile dispatch = &TV2C685_write_overlay;
    dispatch(&original);
    TV2C685_copy_cell(&copied, &original);
    dfb_sink_int(copied.payload);
}


struct TV2C686_Cell {
    int payload;
    int decoy;
};

TV2_NOINLINE static void TV2C686_fill_copy(TV2C686_Cell* dst) {
    TV2C686_Cell staged{};
    staged.payload = dfb_source_A();
    staged.decoy = dfb_source_B();
    *dst = staged;
}

TV2_NOINLINE static void TV2C686_overwrite_decoy(TV2C686_Cell* dst) {
    unsigned char* base = reinterpret_cast<unsigned char*>(dst);
    int* decoy_lane = reinterpret_cast<int*>(base + offsetof(TV2C686_Cell, decoy));
    *decoy_lane = dfb_source_C();
}

extern "C" TV2_NOINLINE void case_TV2C686_heap_copy_callback_decoy_overwrite() {
    TV2C686_Cell* cell = new TV2C686_Cell{};
    TV2C686_fill_copy(cell);

    using Mutator = void (*)(TV2C686_Cell*);
    Mutator callback = &TV2C686_overwrite_decoy;
    callback(cell);

    unsigned char* base = reinterpret_cast<unsigned char*>(cell);
    int* payload_lane = reinterpret_cast<int*>(base + offsetof(TV2C686_Cell, payload));
    const int value = *payload_lane;
    dfb_sink_int(value);
    delete cell;
}


struct TV2C687_Frame {
    unsigned short lane[2];
    int decoy;
};

typedef void (*TV2C687_Writer)(void *, unsigned int, unsigned int);

static TV2_NOINLINE void TV2C687_write_lane(void *base, unsigned int lane, unsigned int value) {
    unsigned char *bytes = static_cast<unsigned char *>(base);
    unsigned short *slot = reinterpret_cast<unsigned short *>(bytes + lane * sizeof(unsigned short));
    *slot = static_cast<unsigned short>(value);
}

static TV2_NOINLINE void TV2C687_write_lane_thunk(void *base, unsigned int lane, unsigned int value) {
    TV2C687_write_lane(base, lane, value);
}

extern "C" TV2_NOINLINE void case_TV2C687_callback_partial_lanes_struct_copy_precision() {
    TV2C687_Frame original = {};
    unsigned int values[2] = {
        static_cast<unsigned int>(dfb_source_A()),
        static_cast<unsigned int>(dfb_source_B())
    };
    original.decoy = dfb_source_C();

    TV2C687_Writer writers[2] = {
        &TV2C687_write_lane,
        &TV2C687_write_lane_thunk
    };
    volatile unsigned int selector = 1u;
    TV2C687_Writer writer = writers[selector & 1u];

    for (unsigned int i = 0; i != 2u; ++i) {
        writer(static_cast<void *>(&original.lane[0]), i, values[i]);
    }

    TV2C687_Frame copied = original;
    unsigned int fused =
        (static_cast<unsigned int>(copied.lane[1]) << 16) |
        static_cast<unsigned int>(copied.lane[0]);
    dfb_sink_int(static_cast<int>(fused));
}


struct TV2C688_Cell {
    int live;
    int dead;
};

typedef void (*TV2C688_Writer)(TV2C688_Cell*, int);

static TV2_NOINLINE void TV2C688_write_plain(TV2C688_Cell* cell, int value) {
    cell->live = value;
}

static TV2_NOINLINE void TV2C688_write_encoded(TV2C688_Cell* cell, int value) {
    int encoded = value ^ 0x13579bdf;
    cell->live = encoded ^ 0x13579bdf;
}

extern "C" TV2_NOINLINE void case_TV2C688_correlated_callback_overwrite_copy(void) {
    int a = dfb_source_A();
    int b = dfb_source_B();
    int c = dfb_source_C();

    TV2C688_Cell cells[2];
    cells[0].live = c;
    cells[0].dead = b;
    cells[1].live = c;
    cells[1].dead = b;

    TV2C688_Writer writers[2] = {
        TV2C688_write_plain,
        TV2C688_write_encoded
    };
    volatile unsigned int route = 1U;
    unsigned int index = route & 1U;
    TV2C688_Cell* selected = &cells[index];
    writers[index](selected, a);

    TV2C688_Cell shadow = *selected;
    unsigned char* dead_bytes = reinterpret_cast<unsigned char*>(&shadow.dead);
    dead_bytes[0] = 0x5aU;
    dfb_sink_int(shadow.live);
}

} /* extern "C" */
