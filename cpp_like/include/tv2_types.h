#pragma once
#include <stdint.h>

/* Testbed V2 Tier 0 — Unreal-like 합성 타입 (설계서 §4).
 * UE 의존성 없이 large / nested / large-padding 레이아웃만 모사한다. */

typedef struct FVectorLike {
    float X;
    float Y;
    float Z;
} FVectorLike;

typedef struct FTransformLike {
    FVectorLike Translation;
    FVectorLike Rotation;
    FVectorLike Scale3D;
} FTransformLike;

typedef struct FTraceInnerLike {
    int Secret;
    int Noise;
} FTraceInnerLike;

/* 큰 패딩(0x100) 뒤에 의미 있는 field가 오는 large struct */
typedef struct FTraceLargeLike {
    char            Padding[0x100];
    FTraceInnerLike Inner;
    int             Other;
    FTransformLike  Transform;
} FTraceLargeLike;

/* 16KB+ 거대 struct (scale 케이스용) */
typedef struct FHugeLike {
    char Padding[0x4000];
    int  Fields[64];
} FHugeLike;
