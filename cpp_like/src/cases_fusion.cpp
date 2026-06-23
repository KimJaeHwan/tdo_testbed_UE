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

} /* extern "C" */
