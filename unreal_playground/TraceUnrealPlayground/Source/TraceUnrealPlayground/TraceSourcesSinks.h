#pragma once
#include "CoreMinimal.h"

/* DataFlowBench 호환 source/sink 경계 (Tier0와 동일 이름).
 * core 엔진은 이 이름을 모르며 BoundaryBinder가 경계로 인식한다.
 * 최적화/심볼 숨김으로 사라지지 않도록 noinline + 외부 linkage + default visibility. */

#if defined(_MSC_VER)
	#define TV2_NOINLINE __declspec(dllexport) __declspec(noinline)
#else
	#define TV2_NOINLINE __attribute__((noinline, used, visibility("default")))
#endif

extern "C" TV2_NOINLINE int  dfb_source_A();
extern "C" TV2_NOINLINE int  dfb_source_B();
extern "C" TV2_NOINLINE int  dfb_source_C();
extern "C" TV2_NOINLINE void dfb_sink_int(int x);
