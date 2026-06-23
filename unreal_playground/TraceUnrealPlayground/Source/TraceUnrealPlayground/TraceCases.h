#pragma once
#include "CoreMinimal.h"
#include "TraceSourcesSinks.h"

/* 모든 케이스를 참조해 링커가 제거하지 못하게 하는 엔트리.
 * 실제 호출할 필요는 없고, 심볼 보존 목적이다(파일 하단 g_keep 참조). */
extern "C" TV2_NOINLINE void TraceRunAll();
