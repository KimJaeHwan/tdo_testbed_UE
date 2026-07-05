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

} /* extern "C" */
