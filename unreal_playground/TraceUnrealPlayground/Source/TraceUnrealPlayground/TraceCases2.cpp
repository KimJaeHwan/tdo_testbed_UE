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
