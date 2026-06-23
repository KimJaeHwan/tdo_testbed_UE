#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Components/ActorComponent.h"
#include "TraceTypes.h"
#include "TraceObjects.generated.h"

/* Testbed V2 Tier2/3 — 라이브 UObject 레이아웃 검증용 UCLASS.
 * 정적 분석은 인스턴스화 없이 함수 본문만으로 가능하므로(케이스는 실행되지 않음),
 * 이 타입들의 인스턴스를 실제로 만들 필요는 없다. UObject 헤더 offset/포인터 체인 레이아웃만 제공. */

UCLASS()
class UTraceSubObject : public UObject
{
	GENERATED_BODY()
public:
	UPROPERTY()
	FTraceInner Inner;
};

UCLASS()
class UTraceComponentLike : public UActorComponent
{
	GENERATED_BODY()
public:
	UPROPERTY()
	FTraceLarge SubStruct;
};

UCLASS()
class ATraceCases : public AActor
{
	GENERATED_BODY()
public:
	UPROPERTY()
	FTraceLarge Payload;            // U008: UObject 헤더 뒤 offset

	UPROPERTY()
	FTraceInner MemberInner;        // U009

	UPROPERTY()
	TObjectPtr<UTraceSubObject> Sub;        // R007: 1-deref

	UPROPERTY()
	TObjectPtr<UTraceComponentLike> Comp;   // R008: 2-deref 체인
};
