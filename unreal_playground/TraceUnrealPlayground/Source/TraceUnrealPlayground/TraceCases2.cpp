#include "TraceCases.h"
#include "TraceTypes.h"
#include "TraceObjects.h"

/* Testbed V2 Tier2/3 — 라이브 UObject / 컨테이너(heap, 2+deref) 케이스.
 * UObject 포인터를 받는 케이스는 인스턴스화 없이 본문만 분석한다(실행되지 않음).
 * anchor = dfb_sink_int arg0. */

// ──────────────── Tier 2: UObject 헤더 offset / 멤버 체인 ────────────────

/* TV2U008 — UObject 헤더 뒤 offset의 field. expect A / forbid B */
extern "C" TV2_NOINLINE void case_TV2U008_uobject_header_offset(ATraceCases* self)
{
	self->Payload.Inner.Secret = dfb_source_A();
	self->Payload.Other        = dfb_source_B();
	dfb_sink_int(self->Payload.Inner.Secret);
}

/* TV2U009 — this->Member 경유. expect A / forbid B */
extern "C" TV2_NOINLINE void case_TV2U009_uobject_member_chain(ATraceCases* self)
{
	self->MemberInner.Secret = dfb_source_A();
	self->MemberInner.Noise  = dfb_source_B();
	dfb_sink_int(self->MemberInner.Secret);
}

// ──────────────── Tier 3: 포인터 체인 (1~2 deref) ────────────────

/* TV2R007 — TObjectPtr 체인: self->Sub->Inner.Secret. expect A / forbid B */
extern "C" TV2_NOINLINE void case_TV2R007_tobjectptr_chain(ATraceCases* self)
{
	self->Sub->Inner.Secret = dfb_source_A();
	self->Sub->Inner.Noise  = dfb_source_B();
	dfb_sink_int(self->Sub->Inner.Secret);
}

/* TV2R008 — 컴포넌트 포인터 2단 체인: self->Comp->SubStruct.Inner.Secret. expect A / forbid B */
extern "C" TV2_NOINLINE void case_TV2R008_component_chain(ATraceCases* self)
{
	self->Comp->SubStruct.Inner.Secret = dfb_source_A();
	self->Comp->SubStruct.Other        = dfb_source_B();
	dfb_sink_int(self->Comp->SubStruct.Inner.Secret);
}

// ──────────────── Tier 3: heap 컨테이너 (2+deref) ────────────────

/* TV2R005 — FString 문자버퍼(heap). expect A / forbid B */
extern "C" TV2_NOINLINE void case_TV2R005_fstring_buffer()
{
	FString S;
	FString T;
	S.AppendChar((TCHAR)dfb_source_A());
	T.AppendChar((TCHAR)dfb_source_B());
	dfb_sink_int((int)S[0]);
}

/* TV2R009 — TMap value field. expect A / forbid B */
extern "C" TV2_NOINLINE void case_TV2R009_tmap_value()
{
	TMap<int32, FTraceItem> M;
	FTraceItem It;
	It.ItemId = dfb_source_A();
	It.Count  = dfb_source_B();
	M.Add(5, It);
	dfb_sink_int(M[5].ItemId);
}

/* TV2R010 — 중첩 컨테이너 TArray<TArray<int32>>: Outer[0][0]. expect A / forbid B */
extern "C" TV2_NOINLINE void case_TV2R010_nested_container()
{
	TArray<TArray<int32>> Outer;
	TArray<int32> Inner0;
	Inner0.Add(dfb_source_A());
	Outer.Add(Inner0);
	TArray<int32> Inner1;
	Inner1.Add(dfb_source_B());
	Outer.Add(Inner1);
	dfb_sink_int(Outer[0][0]);
}

/* TV2R011 — TArray of large struct: Arr[0].Inner.Secret. expect A / forbid B */
extern "C" TV2_NOINLINE void case_TV2R011_tarray_large_elem()
{
	TArray<FTraceLarge> Arr;
	FTraceLarge L;
	L.Inner.Secret = dfb_source_A();
	L.Other        = dfb_source_B();
	Arr.Add(L);
	dfb_sink_int(Arr[0].Inner.Secret);
}

/* TV2R006 — FName layout noise: FName 뒤 int field offset 추적. expect A / forbid B */
extern "C" TV2_NOINLINE void case_TV2R006_fname_layout()
{
	FTraceNamed s;
	s.Tag    = FName(TEXT("trace"));   // FName = layout noise
	s.Secret = dfb_source_A();
	s.Noise  = dfb_source_B();
	dfb_sink_int(s.Secret);
}

/* TV2R012 — FVector copy (P1에서 SIMD lowering). expect A / forbid B */
extern "C" TV2_NOINLINE void case_TV2R012_fvector_simd()
{
	FVector A(0.0, 0.0, 0.0);
	A.X = (double)dfb_source_A();
	A.Y = (double)dfb_source_B();
	FVector B = A;
	dfb_sink_int((int)B.X);
}

// ───────────────────────── keep-alive ─────────────────────────
// 실행되지 않는다(포인터 인자는 분석용 placeholder). 심볼 보존 목적.

extern "C" TV2_NOINLINE void case_TV2R201_tarray_realloc_indexed_read_wrong_index();
extern "C" TV2_NOINLINE void case_TV2R202_tarray_struct_field_neighbor_kill_after_realloc();
extern "C" TV2_NOINLINE void case_TV2R301_tarray_swap_remove_reindexed_field();
extern "C" TV2_NOINLINE void case_TV2R302_tmap_fname_wrong_key_field();
extern "C" TV2_NOINLINE void case_TV2R303_tarray_alias_callback_field_write();

extern "C" TV2_NOINLINE void case_TV2R304_ue_callback_heap_field_precision();
extern "C" TV2_NOINLINE void case_TV2R305_callback_write_read_field_precision();
extern "C" TV2_NOINLINE void case_TV2R306_global_callback_field_precise();
extern "C" TV2_NOINLINE void case_TV2R307_ue_computed_mutator_heap_field();
extern "C" TV2_NOINLINE void case_TV2R308_callback_store_then_field_read();
extern "C" TV2_NOINLINE void case_TV2R309_global_computed_callback_heap_overwrite();
extern "C" TV2_NOINLINE void case_TV2R310_ue_callback_heap_payload();
extern "C" TV2_NOINLINE void case_TV2R311_ue_summary_computed_reader_field();
extern "C" TV2_NOINLINE void case_TV2R312_heap_callback_chain_overwrite();
extern "C" TV2_NOINLINE void case_TV2R313_ue_indirect_writer_field_guard();
extern "C" TV2_NOINLINE void case_TV2R314_heap_slot_indirect_field_precise();
extern "C" TV2_NOINLINE void case_TV2R315_tarray_heap_field_kill();
extern "C" TV2_NOINLINE void case_TV2R316_indirect_local_struct_field();
extern "C" TV2_NOINLINE void case_TV2R317_indexed_heap_lane_noise();
extern "C" TV2_NOINLINE void case_TV2R318_heap_struct_indirect_reader_noise();
extern "C" TV2_NOINLINE void case_TV2R319_heap_struct_callback_decoy_lane();
extern "C" TV2_NOINLINE void case_TV2R320_heap_select_payload();
extern "C" TV2_NOINLINE void case_TV2R321_heap_dispatch_field_kill();
extern "C" TV2_NOINLINE void case_TV2R322_heap_field_overwrite_opaque_branch();
extern "C" TV2_NOINLINE void case_TV2R323_funcptr_live_field_overwrite();
extern "C" TV2_NOINLINE void case_TV2R324_heap_payload_noise_cross_field();
extern "C" TV2_NOINLINE void case_TV2R325_heap_field_survives_shadow_noise();
extern "C" TV2_NOINLINE void case_TV2R326_heap_alias_selected_node();
extern "C" TV2_NOINLINE void case_TV2R327_masked_node_payload();
extern "C" TV2_NOINLINE void case_TV2R328_indirect_node_pick_payload();
extern "C" TV2_NOINLINE void case_TV2R329_tarray_swap_remove_live_tail_payload();
extern "C" TV2_NOINLINE void case_TV2R330_heap_selected_node_payload();
extern "C" TV2_NOINLINE void case_TV2R331_heap_alias_selected_node();
extern "C" TV2_NOINLINE void case_TV2R332_heap_alias_stale_copy_kill();
extern "C" TV2_NOINLINE void case_TV2R333_static_alias_overwrite_no_source();
extern "C" TV2_NOINLINE void case_TV2R334_heap_alias_negative_after_overwrite();
extern "C" TV2_NOINLINE void case_TV2R335_tarray_selected_payload_kills_noise();
extern "C" TV2_NOINLINE void case_TV2R336_heap_selected_node_payload_kill();
extern "C" TV2_NOINLINE void case_TV2R337_heap_alias_selected_node_multisink();
extern "C" TV2_NOINLINE void case_TV2R338_heap_alias_negative_stale();
extern "C" TV2_NOINLINE void case_TV2R339_heap_alias_selected_node_payload();
extern "C" TV2_NOINLINE void case_TV2R340_heap_alias_selected_node_no_flow();
extern "C" TV2_NOINLINE void TraceRunAll2()
{
	case_TV2U008_uobject_header_offset(nullptr);
	case_TV2U009_uobject_member_chain(nullptr);
	case_TV2R007_tobjectptr_chain(nullptr);
	case_TV2R008_component_chain(nullptr);
	case_TV2R005_fstring_buffer();
	case_TV2R009_tmap_value();
	case_TV2R010_nested_container();
	case_TV2R011_tarray_large_elem();
	case_TV2R006_fname_layout();
	case_TV2R012_fvector_simd();
	case_TV2R201_tarray_realloc_indexed_read_wrong_index();
	case_TV2R202_tarray_struct_field_neighbor_kill_after_realloc();
	case_TV2R301_tarray_swap_remove_reindexed_field();
	case_TV2R302_tmap_fname_wrong_key_field();
	case_TV2R303_tarray_alias_callback_field_write();
	case_TV2R304_ue_callback_heap_field_precision();
	case_TV2R305_callback_write_read_field_precision();
	case_TV2R306_global_callback_field_precise();
	case_TV2R307_ue_computed_mutator_heap_field();
	case_TV2R308_callback_store_then_field_read();
	case_TV2R309_global_computed_callback_heap_overwrite();
	case_TV2R310_ue_callback_heap_payload();
	case_TV2R311_ue_summary_computed_reader_field();
	case_TV2R312_heap_callback_chain_overwrite();
	case_TV2R313_ue_indirect_writer_field_guard();
	case_TV2R314_heap_slot_indirect_field_precise();
	case_TV2R315_tarray_heap_field_kill();
	case_TV2R316_indirect_local_struct_field();
	case_TV2R317_indexed_heap_lane_noise();
	case_TV2R318_heap_struct_indirect_reader_noise();
	case_TV2R319_heap_struct_callback_decoy_lane();
	case_TV2R320_heap_select_payload();
	case_TV2R321_heap_dispatch_field_kill();
	case_TV2R322_heap_field_overwrite_opaque_branch();
	case_TV2R323_funcptr_live_field_overwrite();
	case_TV2R324_heap_payload_noise_cross_field();
	case_TV2R325_heap_field_survives_shadow_noise();
	case_TV2R326_heap_alias_selected_node();
	case_TV2R327_masked_node_payload();
	case_TV2R328_indirect_node_pick_payload();
	case_TV2R329_tarray_swap_remove_live_tail_payload();
	case_TV2R330_heap_selected_node_payload();
	case_TV2R331_heap_alias_selected_node();
	case_TV2R332_heap_alias_stale_copy_kill();
	case_TV2R333_static_alias_overwrite_no_source();
	case_TV2R334_heap_alias_negative_after_overwrite();
	case_TV2R335_tarray_selected_payload_kills_noise();
	case_TV2R336_heap_selected_node_payload_kill();
	case_TV2R337_heap_alias_selected_node_multisink();
	case_TV2R338_heap_alias_negative_stale();
	case_TV2R339_heap_alias_selected_node_payload();
	case_TV2R340_heap_alias_selected_node_no_flow();
}

static void (*volatile g_tv2_keep2)() = &TraceRunAll2;

/* TV2R201 — TArray reallocation + same-index overwrite. expect C / forbid A,B */
extern "C" TV2_NOINLINE void case_TV2R201_tarray_realloc_indexed_read_wrong_index()
{
    TArray<FTraceItem> Items;
    Items.Reserve(1);

    FTraceItem A;
    FTraceItem B;
    FTraceItem C;
    A.ItemId = dfb_source_A();
    B.ItemId = dfb_source_B();
    C.ItemId = dfb_source_C();

    Items.Add(A);
    Items.Add(B);

    // Force backing-store growth after the first two element writes.
    for (int32 I = 0; I < 64; ++I)
    {
        FTraceItem Padding;
        Padding.ItemId = 0;
        Padding.Count = 0;
        Items.Add(Padding);
    }

    Items[1] = C;
    dfb_sink_int(Items[1].ItemId);
}

/* TV2R202 — TArray reallocation + neighbor-field kill. expect A / forbid B,C */
extern "C" TV2_NOINLINE void case_TV2R202_tarray_struct_field_neighbor_kill_after_realloc()
{
    TArray<FTraceInner> Inners;
    Inners.Reserve(1);

    FTraceInner First;
    FTraceInner Second;
    First.Secret = dfb_source_A();
    First.Noise = dfb_source_B();
    Second.Secret = dfb_source_C();
    Second.Noise = 0;

    Inners.Add(First);

    // Force backing-store growth while preserving element identity.
    for (int32 I = 0; I < 64; ++I)
    {
        FTraceInner Padding;
        Padding.Secret = 0;
        Padding.Noise = 0;
        Inners.Add(Padding);
    }

    Inners[0].Noise = 0;
    Inners.Add(Second);
    dfb_sink_int(Inners[0].Secret);
}

/* TV2R301 - TArray swap/remove reindexes element. expect C / forbid A,B */
extern "C" TV2_NOINLINE void case_TV2R301_tarray_swap_remove_reindexed_field()
{
    TArray<FTraceItem> Items;
    Items.Reserve(1);

    FTraceItem A;
    FTraceItem B;
    FTraceItem C;
    A.ItemId = dfb_source_A();
    A.Count = 0;
    B.ItemId = dfb_source_B();
    B.Count = 0;
    C.ItemId = dfb_source_C();
    C.Count = 0;

    Items.Add(A);
    Items.Add(B);
    Items.Add(C);

    for (int32 I = 0; I < 32; ++I)
    {
        FTraceItem Padding;
        Padding.ItemId = 0;
        Padding.Count = I;
        Items.Add(Padding);
    }

    Items.Swap(0, 2);
    Items.RemoveAt(1, 1, EAllowShrinking::No);
    dfb_sink_int(Items[0].ItemId);
}

/* TV2R302 - TMap FName wrong-key field. expect A / forbid B,C */
extern "C" TV2_NOINLINE void case_TV2R302_tmap_fname_wrong_key_field()
{
    TMap<FName, FTraceItem> Map;

    FTraceItem Target;
    FTraceItem Noise;
    Target.ItemId = dfb_source_A();
    Target.Count = dfb_source_B();
    Noise.ItemId = dfb_source_C();
    Noise.Count = 0;

    Map.Add(FName(TEXT("target")), Target);
    Map.Add(FName(TEXT("noise")), Noise);

    FTraceItem *Found = Map.Find(FName(TEXT("target")));
    if (Found)
    {
        Found->Count = 0;
        dfb_sink_int(Found->ItemId);
    }
}

struct FTV2R303Item { int32 Key; int32 Payload; int32 Guard; };
using FTV2R303Writer = void (*)(FTV2R303Item*, int32);
static void tv2_write_alias_payload(FTV2R303Item* Item, int32 Value) { Item->Payload = Value; }
extern "C" TV2_NOINLINE void case_TV2R303_tarray_alias_callback_field_write() {
  TArray<FTV2R303Item> Items;
  Items.Add({dfb_source_B(), 0, dfb_source_C()});
  FTV2R303Item* Alias = &Items[0];
  FTV2R303Writer Writer = tv2_write_alias_payload;
  Writer(Alias, dfb_source_A());
  int32 Observed = Items[0].Payload;
  dfb_sink_int(Observed);
}

struct TV2R304_Cell {
    int First;
    int Second;
};

typedef void (*TV2R304_Writer)(TV2R304_Cell*, int);

extern "C" TV2_NOINLINE void tv2r304_write_second(TV2R304_Cell* Cell, int Value) {
    Cell->Second = Value + 17;
}

extern "C" TV2_NOINLINE void tv2r304_write_first(TV2R304_Cell* Cell, int Value) {
    Cell->First = Value ^ 0x55;
}

extern "C" TV2_NOINLINE void case_TV2R304_ue_callback_heap_field_precision() {
    TV2R304_Cell* Cell = new TV2R304_Cell();
    Cell->First = dfb_source_B();
    Cell->Second = dfb_source_C();
    TV2R304_Writer Writers[2] = { tv2r304_write_first, tv2r304_write_second };
    TV2R304_Writer Writer = Writers[0];
    Writer(Cell, dfb_source_A());
    dfb_sink_int(Cell->First);
    delete Cell;
}

struct TV2R305_Node {
    int payload;
    int noise;
};

typedef void (*TV2R305_WriteFn)(TV2R305_Node *node, int value);
typedef int (*TV2R305_ReadFn)(TV2R305_Node *node);

extern "C" TV2_NOINLINE void TV2R305_write_payload(TV2R305_Node *node, int value) {
    node->payload = value;
}

extern "C" TV2_NOINLINE void TV2R305_write_noise(TV2R305_Node *node, int value) {
    node->noise = value;
}

extern "C" TV2_NOINLINE int TV2R305_read_payload(TV2R305_Node *node) {
    return node->payload;
}

extern "C" TV2_NOINLINE void case_TV2R305_callback_write_read_field_precision() {
    TV2R305_Node node;
    node.payload = dfb_source_A();
    node.noise = dfb_source_B();

    TV2R305_WriteFn writers[2];
    writers[0] = TV2R305_write_payload;
    writers[1] = TV2R305_write_noise;
    TV2R305_ReadFn reader = TV2R305_read_payload;

    unsigned slot = ((unsigned)node.noise + 7u) & 0u;
    writers[slot](&node, dfb_source_C());
    int value = reader(&node);
    dfb_sink_int(value);
}

struct TV2R306_Cell {
    int chosen;
    int decoy;
};

static TV2R306_Cell GTV2R306_Cell;
typedef void (*TV2R306_Writer)(TV2R306_Cell*);

TV2_NOINLINE static void tv2r306_store_chosen(TV2R306_Cell* cell) {
    int a = dfb_source_A();
    int b = dfb_source_B();
    cell->decoy = b;
    cell->chosen = a;
}

TV2_NOINLINE static void tv2r306_store_decoy(TV2R306_Cell* cell) {
    int c = dfb_source_C();
    cell->decoy = c;
}

extern "C" TV2_NOINLINE void case_TV2R306_global_callback_field_precise(void) {
    GTV2R306_Cell.chosen = 0;
    GTV2R306_Cell.decoy = 0;
    TV2R306_Writer writer = tv2r306_store_chosen;
    writer(&GTV2R306_Cell);
    tv2r306_store_decoy(&GTV2R306_Cell);
    GTV2R306_Cell.decoy = 0x3060;
    dfb_sink_int(GTV2R306_Cell.chosen);
}

struct TV2R307Payload {
    int Header;
    int Live;
    int Noise;
};

using TV2R307Mutator = void (*)(TV2R307Payload*, int, int);

static TV2_NOINLINE void tv2r307_mutate_live(TV2R307Payload* payload, int live, int noise) {
    payload->Noise = noise;
    payload->Live = live;
}

static TV2_NOINLINE void tv2r307_mutate_noise(TV2R307Payload* payload, int live, int noise) {
    payload->Live = noise;
    payload->Noise = live;
}

static TV2_NOINLINE TV2R307Mutator tv2r307_resolve_mutator(int tag) {
    volatile int folded = (tag + 7) - 7;
    return (folded == 3) ? tv2r307_mutate_live : tv2r307_mutate_noise;
}

extern "C" TV2_NOINLINE void case_TV2R307_ue_computed_mutator_heap_field(void) {
    TV2R307Payload* payload = new TV2R307Payload{0, 0, 0};
    int live = dfb_source_A();
    int noise = dfb_source_C();
    TV2R307Mutator mutator = tv2r307_resolve_mutator(3);
    mutator(payload, live, noise);
    dfb_sink_int(payload->Live);
    delete payload;
}

struct TV2R308_Record {
  int Hot;
  int Cold;
};

typedef void (*TV2R308_Callback)(TV2R308_Record *, int);

static TV2_NOINLINE void tv2r308_store_hot(TV2R308_Record *record, int value) {
  record->Hot = value;
}

static TV2_NOINLINE void tv2r308_store_cold(TV2R308_Record *record, int value) {
  record->Cold = value;
}

static TV2_NOINLINE TV2R308_Callback tv2r308_choose_callback(int token) {
  volatile int folded = (token * 3) - 21;
  if (folded == 0) {
    return &tv2r308_store_hot;
  }
  return &tv2r308_store_cold;
}

extern "C" TV2_NOINLINE void case_TV2R308_callback_store_then_field_read(void) {
  TV2R308_Record record;
  record.Hot = 0;
  record.Cold = dfb_source_B();

  TV2R308_Callback callback = tv2r308_choose_callback(7);
  callback(&record, dfb_source_A());

  int value = record.Hot;
  dfb_sink_int(value);
}

struct TV2R309Packet {
    int lane0;
    int lane1;
    int noise;
};

typedef void (*TV2R309Mutator)(TV2R309Packet*);
static TV2R309Mutator GTV2R309Mutator;

TV2_NOINLINE static void tv2r309_write_chosen(TV2R309Packet* P) {
    P->lane0 = dfb_source_A();
}

TV2_NOINLINE static void tv2r309_write_decoy(TV2R309Packet* P) {
    P->lane0 = dfb_source_C();
}

extern "C" TV2_NOINLINE void case_TV2R309_global_computed_callback_heap_overwrite(void) {
    TV2R309Packet* Chosen = new TV2R309Packet();
    TV2R309Packet* Decoy = new TV2R309Packet();

    Chosen->lane0 = dfb_source_B();
    Chosen->lane1 = 0x3091;
    Chosen->noise = 0x3092;
    Decoy->lane0 = dfb_source_C();
    Decoy->lane1 = dfb_source_B();
    Decoy->noise = 0x3093;

    volatile int Guard = 0;
    GTV2R309Mutator = Guard ? tv2r309_write_decoy : tv2r309_write_chosen;
    GTV2R309Mutator(Chosen);

    dfb_sink_int(Chosen->lane0);

    delete Chosen;
    delete Decoy;
}

struct TV2R310_Node {
    int payload;
    int noise;
};

typedef void (*TV2R310_WriteFn)(TV2R310_Node*, int);

static TV2_NOINLINE void tv2r310_write_payload(TV2R310_Node* node, int value) {
    node->payload = value;
}

static TV2_NOINLINE void tv2r310_write_noise(TV2R310_Node* node, int value) {
    node->noise = value;
}

extern "C" TV2_NOINLINE void case_TV2R310_ue_callback_heap_payload(void) {
    TV2R310_Node* node = new TV2R310_Node();
    node->payload = 0;
    node->noise = 0;
    TV2R310_WriteFn writers[2] = {tv2r310_write_noise, tv2r310_write_payload};
    int live = dfb_source_A();
    int noise = dfb_source_B();
    writers[0](node, noise);
    writers[1](node, live);
    node->noise = dfb_source_C();
    dfb_sink_int(node->payload);
    delete node;
}

struct TV2R311_Packet {
    int cold;
    int hot;
};

using TV2R311_SelectFn = int (*)(TV2R311_Packet *);

static TV2_NOINLINE int tv2r311_read_hot(TV2R311_Packet *packet) {
    return packet->hot;
}

static TV2_NOINLINE int tv2r311_read_cold(TV2R311_Packet *packet) {
    return packet->cold;
}

static TV2_NOINLINE void tv2r311_store_packet(TV2R311_Packet *packet, int hot, int cold) {
    packet->hot = hot;
    packet->cold = cold;
}

extern "C" TV2_NOINLINE void case_TV2R311_ue_summary_computed_reader_field(void) {
    TV2R311_Packet packet = {0, 0};
    TV2R311_SelectFn readers[2] = {tv2r311_read_cold, tv2r311_read_hot};
    int live = dfb_source_A();
    int noise = dfb_source_B();
    tv2r311_store_packet(&packet, live, noise);
    int out = readers[1](&packet);
    dfb_sink_int(out);
}

struct TV2R312_Node { int payload; int noise; TV2R312_Node* next; };

TV2_NOINLINE void tv2r312_write_payload(TV2R312_Node* node, int value) {
    node->payload = value;
}

TV2_NOINLINE void tv2r312_write_noise(TV2R312_Node* node, int value) {
    node->noise = value;
}

extern "C" TV2_NOINLINE void case_TV2R312_heap_callback_chain_overwrite(void) {
    TV2R312_Node* first = new TV2R312_Node();
    TV2R312_Node* second = new TV2R312_Node();
    first->payload = dfb_source_B();
    first->noise = dfb_source_C();
    first->next = second;
    second->payload = dfb_source_C();
    second->noise = dfb_source_B();
    void (*writer)(TV2R312_Node*, int) = tv2r312_write_payload;
    tv2r312_write_noise(first->next, dfb_source_B());
    writer(first->next, dfb_source_A());
    dfb_sink_int(first->next->payload);
    delete second;
    delete first;
}

namespace {
struct TV2R313_Box {
    int payload;
    int decoy;
};

typedef void (*TV2R313_Writer)(TV2R313_Box*);

TV2_NOINLINE void TV2R313_write_decoy(TV2R313_Box* box) {
    box->decoy = dfb_source_B();
}

TV2_NOINLINE void TV2R313_write_payload(TV2R313_Box* box) {
    box->payload = dfb_source_A();
}

TV2_NOINLINE TV2R313_Writer TV2R313_resolve_writer(int token) {
    TV2R313_Writer first = TV2R313_write_decoy;
    TV2R313_Writer second = TV2R313_write_payload;
    return ((token + 7) == 42) ? second : first;
}
}

extern "C" TV2_NOINLINE void case_TV2R313_ue_indirect_writer_field_guard(void) {
    TV2R313_Box box = { 0, 0 };
    TV2R313_Writer writer = TV2R313_resolve_writer(35);
    writer(&box);
    TV2R313_write_decoy(&box);
    dfb_sink_int(box.payload);
}

struct TV2R314Box {
    int Primary;
    int Secondary;
};

TV2_NOINLINE static void tv2r314_write_primary(TV2R314Box* box, int value) {
    box->Primary = value;
}

TV2_NOINLINE static int tv2r314_read_indirect(TV2R314Box** slots, int index) {
    TV2R314Box* picked = slots[index];
    return picked->Primary;
}

extern "C" TV2_NOINLINE void case_TV2R314_heap_slot_indirect_field_precise(void) {
    TV2R314Box* aBox = new TV2R314Box();
    TV2R314Box* bBox = new TV2R314Box();
    aBox->Primary = 0;
    aBox->Secondary = 0;
    bBox->Primary = 0;
    bBox->Secondary = 0;

    int a = dfb_source_A();
    int b = dfb_source_B();
    int c = dfb_source_C();

    tv2r314_write_primary(aBox, a);
    tv2r314_write_primary(bBox, b);
    aBox->Primary = 0x7070;
    aBox->Secondary = c;
    bBox->Secondary = c ^ 0x55;

    TV2R314Box* slots[2];
    slots[0] = aBox;
    slots[1] = bBox;
    int out = tv2r314_read_indirect(slots, 1);
    dfb_sink_int(out);

    delete aBox;
    delete bBox;
}

struct TV2R315_Cell {
    int live;
    int dead;
};

static TV2_NOINLINE void TV2R315_fill(TV2R315_Cell* cells, int index, int live, int dead) {
    cells[index].dead = dead;
    cells[index].live = live;
}

static TV2_NOINLINE int TV2R315_pick_live(TV2R315_Cell* cells, int index) {
    return cells[index].live;
}

extern "C" TV2_NOINLINE void case_TV2R315_tarray_heap_field_kill() {
    TArray<TV2R315_Cell> cells;
    cells.SetNum(3);
    int a = dfb_source_A();
    int b = dfb_source_B();
    int c = dfb_source_C();
    TV2R315_fill(cells.GetData(), 1, a, b);
    cells[1].dead = c;
    int out = TV2R315_pick_live(cells.GetData(), 1);
    dfb_sink_int(out);
}

struct TV2R316_Box {
    int head;
    int tail;
    int scratch;
};

typedef void (*TV2R316_WriteFn)(TV2R316_Box*, int, int);

static TV2_NOINLINE void tv2r316_write_head(TV2R316_Box* box, int live, int decoy) {
    box->scratch = decoy ^ 0x44;
    box->head = live + 5;
}

static TV2_NOINLINE void tv2r316_write_tail(TV2R316_Box* box, int live, int decoy) {
    box->tail = decoy + live;
}

extern "C" TV2_NOINLINE void case_TV2R316_indirect_local_struct_field(void) {
    TV2R316_Box box = {0, 0, 0};
    int a = dfb_source_A();
    int b = dfb_source_B();
    TV2R316_WriteFn fn = tv2r316_write_head;
    fn(&box, a, b);
    tv2r316_write_tail(&box, 7, b);
    box.tail = 0x515151;
    dfb_sink_int(box.head);
}

struct TV2R317_Payload {
  int slots[3];
};

static TV2_NOINLINE int TV2R317_load_indexed(TV2R317_Payload* payload, int idx) {
  int bounded = idx & 1;
  return payload->slots[bounded + 1];
}

extern "C" TV2_NOINLINE void case_TV2R317_indexed_heap_lane_noise(void) {
  TV2R317_Payload* payload = new TV2R317_Payload();
  payload->slots[0] = dfb_source_B();
  payload->slots[1] = dfb_source_A();
  payload->slots[2] = dfb_source_C();
  payload->slots[2] = 0x3170;
  int idx = payload->slots[2] & 0;
  int out = TV2R317_load_indexed(payload, idx);
  dfb_sink_int(out);
  delete payload;
}

struct TV2R318_Node {
    int live;
    int noise;
};

typedef int (*TV2R318_ReadFn)(TV2R318_Node *);

TV2_NOINLINE static void tv2r318_store_live(TV2R318_Node *node, int v) {
    node->live = v;
}

TV2_NOINLINE static int tv2r318_read_live(TV2R318_Node *node) {
    return node->live;
}

TV2_NOINLINE static int tv2r318_read_noise(TV2R318_Node *node) {
    return node->noise;
}

extern "C" TV2_NOINLINE void case_TV2R318_heap_struct_indirect_reader_noise(void) {
    TV2R318_Node *node = new TV2R318_Node();
    node->live = 0;
    node->noise = dfb_source_C();
    tv2r318_store_live(node, dfb_source_A());
    node->noise = 0x33333333;
    TV2R318_ReadFn reader = tv2r318_read_live;
    dfb_sink_int(reader(node));
    delete node;
}

struct TV2R319_Cell {
    int payload;
    int decoy;
};

static TV2_NOINLINE void tv2r319_stage_payload(TV2R319_Cell *cell, int v) {
    cell->payload = v;
}

static TV2_NOINLINE int tv2r319_read_payload(const TV2R319_Cell *cell) {
    return cell->payload;
}

extern "C" TV2_NOINLINE void case_TV2R319_heap_struct_callback_decoy_lane() {
    TV2R319_Cell *cell = new TV2R319_Cell();
    cell->payload = 0;
    cell->decoy = 0;
    int a = dfb_source_A();
    int b = dfb_source_B();
    int c = dfb_source_C();
    void (*stage)(TV2R319_Cell *, int) = tv2r319_stage_payload;
    stage(cell, a);
    cell->decoy = b;
    if ((c | 1) != 0) {
        cell->decoy ^= c;
    }
    int out = tv2r319_read_payload(cell);
    dfb_sink_int(out);
    delete cell;
}

struct TV2R320_Node {
    int Payload;
    int Shadow;
};

TV2_NOINLINE static TV2R320_Node* tv2r320_select_node(TV2R320_Node* first, TV2R320_Node* second, int selector) {
    return selector ? second : first;
}

TV2_NOINLINE static int tv2r320_read_payload(TV2R320_Node* n) {
    return n->Payload;
}

extern "C" TV2_NOINLINE void case_TV2R320_heap_select_payload(void) {
    TV2R320_Node* left = new TV2R320_Node();
    TV2R320_Node* right = new TV2R320_Node();
    int a = dfb_source_A();
    int b = dfb_source_B();
    int c = dfb_source_C();
    left->Payload = a;
    left->Shadow = c;
    right->Payload = b;
    right->Shadow = c ^ 0x55aa55aa;
    TV2R320_Node* chosen = tv2r320_select_node(left, right, 1);
    int out = tv2r320_read_payload(chosen);
    dfb_sink_int(out);
    delete left;
    delete right;
}

struct TV2R321_Cell {
    int live;
    int shadow;
};

typedef void (*TV2R321_WriteFn)(TV2R321_Cell*, int, int);

TV2_NOINLINE static void tv2r321_write_selected(TV2R321_Cell* cell, int live_value, int shadow_value) {
    cell->shadow = shadow_value;
    cell->live = live_value;
}

TV2_NOINLINE static void tv2r321_write_decoy(TV2R321_Cell* cell, int decoy_value, int shadow_value) {
    cell->shadow = decoy_value ^ shadow_value;
}

TV2_NOINLINE static int tv2r321_pick_writer(void) {
    return (sizeof(TV2R321_Cell) == (2 * sizeof(int))) ? 0 : 1;
}

extern "C" TV2_NOINLINE void case_TV2R321_heap_dispatch_field_kill(void) {
    int a = dfb_source_A();
    int b = dfb_source_B();
    int c = dfb_source_C();

    TV2R321_Cell* cell = new TV2R321_Cell();
    cell->live = a;
    cell->shadow = c;

    TV2R321_WriteFn table[2] = { tv2r321_write_selected, tv2r321_write_decoy };
    table[tv2r321_pick_writer()](cell, b, c);

    int out = cell->live ^ 0x31;
    dfb_sink_int(out);
    delete cell;
}

struct TV2R322_Node {
  int Payload;
  int Shadow;
};

static TV2_NOINLINE void tv2r322_seed_node(TV2R322_Node *node, int a, int b) {
  node->Payload = a;
  node->Shadow = a ^ 0x13579;
  if ((node->Shadow | 1) != 0) {
    node->Payload = b;
  }
}

extern "C" TV2_NOINLINE void case_TV2R322_heap_field_overwrite_opaque_branch(void) {
  TV2R322_Node *node = new TV2R322_Node();
  int a = dfb_source_A();
  int b = dfb_source_B();
  tv2r322_seed_node(node, a, b);
  int out = node->Payload;
  delete node;
  dfb_sink_int(out);
}

struct TV2R323_Payload {
    int stable;
    int live;
    int noise;
};

typedef void (*TV2R323Writer)(TV2R323_Payload*, int);

static TV2_NOINLINE void tv2r323_write_live(TV2R323_Payload* p, int v) {
    p->live = v;
}

static TV2_NOINLINE void tv2r323_write_noise(TV2R323_Payload* p, int v) {
    p->noise = v;
}

extern "C" TV2_NOINLINE void case_TV2R323_funcptr_live_field_overwrite(void) {
    TV2R323_Payload p;
    p.stable = dfb_source_B();
    p.live = dfb_source_A();
    p.noise = 0x3230;
    TV2R323Writer writer = tv2r323_write_live;
    writer(&p, dfb_source_C());
    tv2r323_write_noise(&p, 0x7777);
    dfb_sink_int(p.live);
}

struct TV2R324_Box {
    int payload;
    int noise;
};

TV2_NOINLINE static void tv2r324_write_payload(TV2R324_Box* box, int value) {
    box->payload = value;
}

TV2_NOINLINE static void tv2r324_write_noise(TV2R324_Box* box, int value) {
    box->noise = value;
}

TV2_NOINLINE static int tv2r324_read_payload(const TV2R324_Box* box) {
    return box->payload;
}

extern "C" TV2_NOINLINE void case_TV2R324_heap_payload_noise_cross_field(void) {
    TV2R324_Box* box = new TV2R324_Box();
    int a = dfb_source_A();
    int b = dfb_source_B();
    int c = dfb_source_C();

    tv2r324_write_payload(box, a);
    tv2r324_write_noise(box, b);
    tv2r324_write_payload(box, c);

    int out = tv2r324_read_payload(box);
    dfb_sink_int(out);
    delete box;
}

struct TV2R325_Node {
    int payload;
    int shadow;
};

static TV2_NOINLINE int TV2R325_pick_payload(TV2R325_Node *node, int selector) {
    int local = node->payload;
    if ((selector & 3) == 1) {
        local ^= 0x2026;
        local ^= 0x2026;
    }
    return local;
}

extern "C" TV2_NOINLINE void case_TV2R325_heap_field_survives_shadow_noise() {
    TV2R325_Node *node = new TV2R325_Node();
    int a = dfb_source_A();
    int b = dfb_source_B();
    node->payload = a;
    node->shadow = b;
    int out = TV2R325_pick_payload(node, b);
    delete node;
    dfb_sink_int(out);
}

struct TV2R326_Node {
    int payload;
    int shadow;
};

static TV2_NOINLINE TV2R326_Node *tv2r326_choose_node(TV2R326_Node *first, TV2R326_Node *second, int selector) {
    if ((selector & 1) == 0) {
        return first;
    }
    return second;
}

extern "C" TV2_NOINLINE void case_TV2R326_heap_alias_selected_node(void) {
    TV2R326_Node left;
    TV2R326_Node right;
    int a = dfb_source_A();
    int b = dfb_source_B();
    left.payload = a;
    left.shadow = b;
    right.payload = b;
    right.shadow = 0x326326;
    TV2R326_Node *picked = tv2r326_choose_node(&left, &right, 2);
    picked->shadow = 0;
    dfb_sink_int(picked->payload);
}

struct TV2R327_Node {
    int payload;
    TV2R327_Node* next;
};

static TV2_NOINLINE TV2R327_Node* TV2R327_pick(TV2R327_Node* first, TV2R327_Node* second, int selector) {
    return ((selector & 7) == 3) ? second : first;
}

extern "C" TV2_NOINLINE void case_TV2R327_masked_node_payload(void) {
    int a = dfb_source_A();
    int b = dfb_source_B();
    int c = dfb_source_C();
    TV2R327_Node left;
    TV2R327_Node right;
    left.payload = b ^ c;
    left.next = &right;
    right.payload = a;
    right.next = &left;
    int selector = (c ^ c) + 3;
    TV2R327_Node* chosen = TV2R327_pick(&left, left.next, selector);
    dfb_sink_int(chosen->payload);
}

struct TV2R328Node {
    int Payload;
    int Tag;
    TV2R328Node* Next;
};

static TV2_NOINLINE TV2R328Node* TV2R328PickNode(TV2R328Node* first, TV2R328Node* second, int guard) {
    TV2R328Node* table[2] = { second, first };
    unsigned idx = ((unsigned)guard | 1u) & 1u;
    return table[idx];
}

extern "C" TV2_NOINLINE void case_TV2R328_indirect_node_pick_payload(void) {
    int a = dfb_source_A();
    int b = dfb_source_B();
    int c = dfb_source_C();
    TV2R328Node first = { a, c, 0 };
    TV2R328Node second = { b, c ^ 0x328, &first };
    first.Next = &second;
    TV2R328Node* chosen = TV2R328PickNode(&first, &second, c);
    dfb_sink_int(chosen->Payload);
}

struct TV2R329_Cell
{
    int Payload;
    int Noise;
};

extern "C" TV2_NOINLINE void case_TV2R329_tarray_swap_remove_live_tail_payload()
{
    TArray<TV2R329_Cell> Cells;
    Cells.Reserve(3);

    TV2R329_Cell Removed;
    Removed.Payload = dfb_source_A();
    Removed.Noise = 101;

    TV2R329_Cell Neighbor;
    Neighbor.Payload = 202;
    Neighbor.Noise = dfb_source_B();

    TV2R329_Cell Tail;
    Tail.Payload = dfb_source_C();
    Tail.Noise = 303;

    Cells.Add(Removed);
    Cells.Add(Neighbor);
    Cells.Add(Tail);

    Cells.RemoveAtSwap(0, 1, EAllowShrinking::No);

    int Out = Cells[0].Payload;
    dfb_sink_int(Out);
}

struct TV2R330_Node {
    int Payload;
    int Decoy;
};

static TV2_NOINLINE TV2R330_Node* case_TV2R330_pick_node(TV2R330_Node* left, TV2R330_Node* right, int selector) {
    return ((selector & 1) == 0) ? left : right;
}

extern "C" TV2_NOINLINE void case_TV2R330_heap_selected_node_payload(void) {
    int live = dfb_source_A();
    int decoy = dfb_source_B();
    int noise = dfb_source_C();
    TV2R330_Node left;
    TV2R330_Node right;
    left.Payload = decoy;
    left.Decoy = noise;
    right.Payload = live;
    right.Decoy = 0x224466;
    TV2R330_Node* picked = case_TV2R330_pick_node(&left, &right, 1);
    left.Payload = 0x1234;
    int out = picked->Payload;
    dfb_sink_int(out);
}

struct TV2R331_Node { int Payload; int Decoy; TV2R331_Node* Next; };

extern "C" TV2_NOINLINE TV2R331_Node* TV2R331_choose_node(TV2R331_Node* left, TV2R331_Node* right, int selector) {
    return ((selector ^ selector) == 0) ? right : left;
}

extern "C" TV2_NOINLINE void case_TV2R331_heap_alias_selected_node(void) {
    int a = dfb_source_A();
    int b = dfb_source_B();
    int c = dfb_source_C();
    TV2R331_Node* left = new TV2R331_Node{b, c, nullptr};
    TV2R331_Node* right = new TV2R331_Node{c, b, nullptr};
    TV2R331_Node* picked = TV2R331_choose_node(left, right, a);
    picked->Payload = a;
    left->Decoy = b;
    right->Decoy = c;
    int out = picked->Payload;
    dfb_sink_int(out);
    delete left;
    delete right;
}

struct TV2R332_Node {
  int payload;
  int decoy;
};

static TV2_NOINLINE void tv2r332_write_payload(TV2R332_Node* n, int v) {
  n->payload = v;
}

static TV2_NOINLINE TV2R332_Node* tv2r332_pick_live(TV2R332_Node* first, TV2R332_Node* second) {
  volatile int pick_first = 1;
  return pick_first ? first : second;
}

extern "C" TV2_NOINLINE void case_TV2R332_heap_alias_stale_copy_kill() {
  TV2R332_Node* first = new TV2R332_Node{0, 0};
  TV2R332_Node* second = new TV2R332_Node{0, 0};
  int a = dfb_source_A();
  int b = dfb_source_B();
  int c = dfb_source_C();
  tv2r332_write_payload(first, a);
  TV2R332_Node stale = *first;
  tv2r332_write_payload(first, b);
  tv2r332_write_payload(second, c);
  TV2R332_Node* live = tv2r332_pick_live(first, second);
  int out = live->payload;
  dfb_sink_int(out);
  delete first;
  delete second;
  (void)stale;
}

struct TV2R333_Node {
    int payload;
    int decoy;
};

static TV2R333_Node GTV2R333_Left;
static TV2R333_Node GTV2R333_Right;

static TV2_NOINLINE TV2R333_Node* TV2R333_pick_left(void) {
    return &GTV2R333_Left;
}

extern "C" TV2_NOINLINE void case_TV2R333_static_alias_overwrite_no_source(void) {
    TV2R333_Node* live = TV2R333_pick_left();
    live->payload = dfb_source_A();
    live->decoy = dfb_source_B();
    GTV2R333_Right.payload = dfb_source_C();
    live->payload = 0x7333;
    live->decoy = 0x7334;
    dfb_sink_int(live->payload);
}

struct TV2R334_Node {
    int payload;
    int decoy;
};

static TV2_NOINLINE TV2R334_Node* tv2r334_pick_node(TV2R334_Node* first, TV2R334_Node* second, int selector) {
    return selector ? second : first;
}

static TV2_NOINLINE void tv2r334_write_payload(TV2R334_Node* node, int value) {
    node->payload = value;
}

static TV2_NOINLINE void tv2r334_write_decoy(TV2R334_Node* node, int value) {
    node->decoy = value;
}

extern "C" TV2_NOINLINE void case_TV2R334_heap_alias_negative_after_overwrite(void) {
    TV2R334_Node* left = new TV2R334_Node{0, 0};
    TV2R334_Node* right = new TV2R334_Node{0, 0};
    TV2R334_Node* chosen = tv2r334_pick_node(left, right, 1);
    int a = dfb_source_A();
    int b = dfb_source_B();
    tv2r334_write_payload(chosen, a);
    tv2r334_write_decoy(left, b);
    chosen->payload = 0x3340;
    dfb_sink_int(chosen->payload);
    delete left;
    delete right;
}

struct TV2R335_Node {
    int Payload;
    int Noise;
};

static TV2_NOINLINE void tv2r335_fill_nodes(TArray<TV2R335_Node>& Nodes) {
    Nodes.SetNum(2);
    Nodes[0].Payload = dfb_source_A();
    Nodes[0].Noise = dfb_source_B();
    Nodes[1].Payload = dfb_source_C();
    Nodes[1].Noise = 0x3350;
}

static TV2_NOINLINE TV2R335_Node* tv2r335_pick_live(TArray<TV2R335_Node>& Nodes) {
    return &Nodes[1];
}

extern "C" TV2_NOINLINE void case_TV2R335_tarray_selected_payload_kills_noise() {
    TArray<TV2R335_Node> Nodes;
    tv2r335_fill_nodes(Nodes);
    TV2R335_Node* Picked = tv2r335_pick_live(Nodes);
    Picked->Noise = 0x3351;
    dfb_sink_int(Picked->Payload);
}

struct TV2R336_Node {
  int Payload;
  int Noise;
};

static TV2_NOINLINE TV2R336_Node* tv2r336_pick_node(TV2R336_Node* left, TV2R336_Node* right, int selector) {
  return selector ? right : left;
}

static TV2_NOINLINE void tv2r336_write_payload(TV2R336_Node* node) {
  node->Payload = dfb_source_A();
}

static TV2_NOINLINE void tv2r336_write_noise_then_kill(TV2R336_Node* node) {
  node->Noise = dfb_source_B();
  node->Noise = 0x3360;
}

extern "C" TV2_NOINLINE void case_TV2R336_heap_selected_node_payload_kill() {
  TV2R336_Node* left = new TV2R336_Node{0, 0};
  TV2R336_Node* right = new TV2R336_Node{0, 0};
  TV2R336_Node* selected = tv2r336_pick_node(left, right, 1);
  tv2r336_write_payload(selected);
  tv2r336_write_noise_then_kill(selected);
  left->Payload = dfb_source_C();
  dfb_sink_int(selected->Payload);
  dfb_sink_int(selected->Noise);
  delete left;
  delete right;
}

struct TV2R337_Node {
    int payload;
    int decoy;
};

static TV2_NOINLINE TV2R337_Node* tv2r337_pick_node(TV2R337_Node* left, TV2R337_Node* right, int selector) {
    return (selector & 1) ? right : left;
}

static TV2_NOINLINE void tv2r337_write_nodes(TV2R337_Node* left, TV2R337_Node* right) {
    left->payload = dfb_source_A();
    right->payload = dfb_source_B();
    right->decoy = dfb_source_C();
    right->decoy = 77;
}

extern "C" TV2_NOINLINE void case_TV2R337_heap_alias_selected_node_multisink() {
    TV2R337_Node* left = new TV2R337_Node{0, 0};
    TV2R337_Node* right = new TV2R337_Node{0, 0};
    tv2r337_write_nodes(left, right);
    TV2R337_Node* selected = tv2r337_pick_node(left, right, 1);
    dfb_sink_int(selected->payload);
    dfb_sink_int(selected->decoy);
    delete left;
    delete right;
}

struct TV2R338_Node {
    int payload;
    int stale;
    TV2R338_Node* alias;
};

static TV2_NOINLINE TV2R338_Node* tv2r338_select(TV2R338_Node* left, TV2R338_Node* right, int selector) {
    return (selector & 1) ? right : left;
}

static TV2_NOINLINE void tv2r338_prepare(TV2R338_Node* left, TV2R338_Node* right) {
    left->payload = dfb_source_A();
    left->stale = dfb_source_B();
    right->payload = 0x3380;
    right->stale = left->stale;
    left->payload = 0x3381;
    left->alias = right;
    right->alias = left;
}

extern "C" TV2_NOINLINE void case_TV2R338_heap_alias_negative_stale(void) {
    TV2R338_Node* left = new TV2R338_Node();
    TV2R338_Node* right = new TV2R338_Node();
    tv2r338_prepare(left, right);
    TV2R338_Node* picked = tv2r338_select(left->alias, right->alias, 0);
    int observed = picked->payload;
    delete right;
    delete left;
    dfb_sink_int(observed);
}

struct TV2R339_Node {
    int payload;
    int noise;
};

TV2_NOINLINE static TV2R339_Node* tv2r339_pick_node(TV2R339_Node* left, TV2R339_Node* right) {
    return right;
}

TV2_NOINLINE static void tv2r339_write_nodes(TV2R339_Node* left, TV2R339_Node* right) {
    left->payload = dfb_source_A();
    left->noise = dfb_source_C();
    right->payload = dfb_source_B();
    right->noise = 0x339;
}

TV2_NOINLINE static int tv2r339_read_payload(TV2R339_Node* node) {
    return node->payload;
}

extern "C" TV2_NOINLINE void case_TV2R339_heap_alias_selected_node_payload() {
    TV2R339_Node* left = new TV2R339_Node();
    TV2R339_Node* right = new TV2R339_Node();
    left->payload = 0;
    left->noise = 0;
    right->payload = 0;
    right->noise = 0;
    tv2r339_write_nodes(left, right);
    TV2R339_Node* selected = tv2r339_pick_node(left, right);
    int value = tv2r339_read_payload(selected);
    dfb_sink_int(value);
    delete left;
    delete right;
}

struct TV2R340_Node {
    int Payload;
    int Noise;
};

TV2_NOINLINE static TV2R340_Node* tv2r340_pick_live(TV2R340_Node* left, TV2R340_Node* right) {
    return (left->Noise == 0x340) ? right : left;
}

TV2_NOINLINE static void tv2r340_write_nodes(TV2R340_Node* first, TV2R340_Node* second) {
    first->Payload = dfb_source_A();
    first->Noise = dfb_source_C();
    second->Payload = dfb_source_B();
    second->Noise = 0x340;
}

extern "C" TV2_NOINLINE void case_TV2R340_heap_alias_selected_node_no_flow(void) {
    TV2R340_Node* first = new TV2R340_Node{0, 0};
    TV2R340_Node* second = new TV2R340_Node{0, 0};
    tv2r340_write_nodes(first, second);
    first->Payload = 0x3401;
    second->Payload = 0x3402;
    TV2R340_Node* picked = tv2r340_pick_live(first, second);
    dfb_sink_int(picked->Payload);
    delete first;
    delete second;
}

