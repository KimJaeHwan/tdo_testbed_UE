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

