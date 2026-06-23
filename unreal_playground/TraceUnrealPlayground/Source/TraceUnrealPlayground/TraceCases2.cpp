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
}

static void (*volatile g_tv2_keep2)() = &TraceRunAll2;
