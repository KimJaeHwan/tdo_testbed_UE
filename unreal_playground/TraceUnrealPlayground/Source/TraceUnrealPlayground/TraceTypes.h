#pragma once
#include "CoreMinimal.h"
#include "TraceTypes.generated.h"

/* Testbed V2 Tier2 — USTRUCT 타입.
 * UHT/UPROPERTY 리플렉션 + UE 실제 레이아웃(정렬/패딩)을 byte-offset 모델이 견디는지 검증.
 * core는 field 이름을 쓰지 않으므로, 이름은 overlay(Phase7)에서만 의미를 가진다. */

USTRUCT()
struct FTraceInner
{
	GENERATED_BODY()

	UPROPERTY()
	int32 Secret = 0;

	UPROPERTY()
	int32 Noise = 0;
};

/* 큰 struct: 앞쪽에 FTransform(큰 정렬/크기)을 두어 Inner가 비-자명 offset에 오게 한다. */
USTRUCT()
struct FTraceLarge
{
	GENERATED_BODY()

	UPROPERTY()
	FTransform Transform;

	UPROPERTY()
	FTraceInner Inner;

	UPROPERTY()
	int32 Other = 0;
};

/* 컨테이너 element 타입 (Tier3) */
USTRUCT()
struct FTraceItem
{
	GENERATED_BODY()

	UPROPERTY()
	int32 ItemId = 0;

	UPROPERTY()
	int32 Count = 0;
};

/* FName을 layout noise로 둔 struct (R006). FName 뒤 int field offset 추적 검증. */
USTRUCT()
struct FTraceNamed
{
	GENERATED_BODY()

	UPROPERTY()
	FName Tag;          // layout noise (FName = 정수 인덱스 2개)

	UPROPERTY()
	int32 Secret = 0;

	UPROPERTY()
	int32 Noise = 0;
};
