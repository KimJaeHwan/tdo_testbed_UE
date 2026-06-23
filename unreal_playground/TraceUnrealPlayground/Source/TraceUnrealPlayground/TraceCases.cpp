#include "TraceCases.h"
#include "TraceTypes.h"

/* Testbed V2 Tier2/3 — Unreal USTRUCT / 컨테이너 fusion 케이스 (GC 불필요분).
 * anchor = dfb_sink_int arg0. 정답은 expected/tv2_unreal.expected.json 참조.
 * 모두 extern "C" free function → 깨끗한 심볼명으로 분석. */

// ───────────────────────── Tier 2: USTRUCT ─────────────────────────

/* TV2U001 — DirectField: USTRUCT 단일 field. expect A / forbid B */
extern "C" TV2_NOINLINE void case_TV2U001_direct_field()
{
	FTraceInner s;
	s.Secret = dfb_source_A();
	s.Noise  = dfb_source_B();
	dfb_sink_int(s.Secret);
}

/* TV2U002 — LargeStructCopy: B=A 후 narrow field. expect A / forbid B */
extern "C" TV2_NOINLINE void case_TV2U002_large_struct_copy()
{
	FTraceLarge A;
	FTraceLarge B;
	A.Inner.Secret = dfb_source_A();
	A.Other        = dfb_source_B();
	B = A;
	dfb_sink_int(B.Inner.Secret);
}

/* TV2U003 — NestedUSTRUCT: FTraceLarge.Inner.Secret. expect A / forbid B */
extern "C" TV2_NOINLINE void case_TV2U003_nested_ustruct()
{
	FTraceLarge A;
	A.Inner.Secret = dfb_source_A();
	A.Other        = dfb_source_B();
	dfb_sink_int(A.Inner.Secret);
}

/* TV2U004 — ReturnBuffer: USTRUCT 값 반환(sret). expect A / forbid B */
static TV2_NOINLINE FTraceLarge tv2_make_tainted_large()
{
	FTraceLarge t;
	t.Inner.Secret = dfb_source_A();
	t.Other        = dfb_source_B();
	return t;
}

extern "C" TV2_NOINLINE void case_TV2U004_return_buffer()
{
	FTraceLarge r = tv2_make_tainted_large();
	dfb_sink_int(r.Inner.Secret);
}

/* TV2U005 — ControlVsDataStructPhi: data{A,B}, control{C}. forbid data C */
extern "C" TV2_NOINLINE void case_TV2U005_control_vs_data_struct_phi()
{
	FTraceLarge B;
	int cond = dfb_source_C();
	if (cond) B.Inner.Secret = dfb_source_A();
	else      B.Inner.Secret = dfb_source_B();
	dfb_sink_int(B.Inner.Secret);
}

/* TV2U006 — PartialOverwriteKill: 복사 후 같은 슬롯 덮어쓰기. expect C / forbid A,B */
extern "C" TV2_NOINLINE void case_TV2U006_partial_overwrite_kill()
{
	FTraceLarge A;
	FTraceLarge B;
	A.Inner.Secret = dfb_source_A();
	A.Other        = dfb_source_B();
	B = A;
	B.Inner.Secret = dfb_source_C();
	dfb_sink_int(B.Inner.Secret);
}

/* TV2U007 — WideCopyNarrowForbidden: 복사 후 다른 슬롯에 B. expect B / forbid A */
extern "C" TV2_NOINLINE void case_TV2U007_wide_copy_narrow_forbidden()
{
	FTraceLarge A;
	FTraceLarge B;
	A.Inner.Secret = dfb_source_A();
	B = A;
	B.Other = dfb_source_B();
	dfb_sink_int(B.Other);
}

/* TV2U010 — UPROPERTY 다수 + 일부만 오염. expect A / forbid B,C */
extern "C" TV2_NOINLINE void case_TV2U010_multi_property_partial()
{
	FTraceLarge A;
	A.Inner.Secret = dfb_source_A();
	A.Inner.Noise  = dfb_source_B();
	A.Other        = dfb_source_C();
	dfb_sink_int(A.Inner.Secret);
}

// ──────────────────── Tier 3: 값 타입 컨테이너 (0-deref) ────────────────────

/* TV2R003 — FVector field: V.X만 오염. expect A / forbid B */
extern "C" TV2_NOINLINE void case_TV2R003_fvector_field()
{
	FVector V(0.0, 0.0, 0.0);
	V.X = (double)dfb_source_A();
	V.Y = (double)dfb_source_B();
	dfb_sink_int((int)V.X);
}

/* TV2R004 — FTransform Translation 왕복. expect A / forbid B */
extern "C" TV2_NOINLINE void case_TV2R004_ftransform_translation()
{
	FTransform T;
	FVector V((double)dfb_source_A(), (double)dfb_source_B(), 0.0);
	T.SetTranslation(V);
	FVector Out = T.GetTranslation();
	dfb_sink_int((int)Out.X);
}

// ──────────────────── Tier 3: TArray (1-deref, heap) ────────────────────

/* TV2R001 — TArray element [상수 index]. expect A / forbid B */
extern "C" TV2_NOINLINE void case_TV2R001_tarray_element()
{
	TArray<FTraceItem> Items;
	FTraceItem It;
	It.ItemId = dfb_source_A();
	It.Count  = dfb_source_B();
	Items.Add(It);
	dfb_sink_int(Items[0].ItemId);
}

/* TV2R002 — TArray wrong-index forbidden. read Items[1]=B → expect B / forbid A */
extern "C" TV2_NOINLINE void case_TV2R002_tarray_wrong_index()
{
	TArray<FTraceItem> Items;
	FTraceItem I0; I0.ItemId = dfb_source_A(); Items.Add(I0);
	FTraceItem I1; I1.ItemId = dfb_source_B(); Items.Add(I1);
	dfb_sink_int(Items[1].ItemId);
}

// ───────────────────────── keep-alive ─────────────────────────

extern "C" TV2_NOINLINE void TraceRunAll()
{
	case_TV2U001_direct_field();
	case_TV2U002_large_struct_copy();
	case_TV2U003_nested_ustruct();
	case_TV2U004_return_buffer();
	case_TV2U005_control_vs_data_struct_phi();
	case_TV2U006_partial_overwrite_kill();
	case_TV2U007_wide_copy_narrow_forbidden();
	case_TV2U010_multi_property_partial();
	case_TV2R003_fvector_field();
	case_TV2R004_ftransform_translation();
	case_TV2R001_tarray_element();
	case_TV2R002_tarray_wrong_index();
}

/* volatile 참조로 TraceRunAll(및 그것이 호출하는 모든 케이스)을 링커가 제거하지 못하게 한다. */
static void (*volatile g_tv2_keep)() = &TraceRunAll;
