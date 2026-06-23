#pragma once
/* Testbed V2 — Tier 0 공통 매크로 (09_tdo_testbed/include/dfbench.h 패턴 재사용) */

#include <stdint.h>
#include <stddef.h>

#if defined(_MSC_VER)
    #define TV2_NOINLINE __declspec(noinline)
    #define TV2_EXPORT   __declspec(dllexport)
    #define TV2_USED
#else
    #define TV2_NOINLINE __attribute__((noinline))
    #define TV2_EXPORT   __attribute__((visibility("default")))
    #define TV2_USED     __attribute__((used))
#endif

/* case/source/sink/helper 함수는 최적화로 사라지지 않도록 export + noinline + used */
#define TV2_CASE   TV2_EXPORT TV2_NOINLINE TV2_USED
#define TV2_SOURCE TV2_EXPORT TV2_NOINLINE TV2_USED
#define TV2_SINK   TV2_EXPORT TV2_NOINLINE TV2_USED
#define TV2_HELPER TV2_EXPORT TV2_NOINLINE TV2_USED

#if defined(__cplusplus)
    #define TV2_EXTERN_C extern "C"
#else
    #define TV2_EXTERN_C
#endif

#if defined(__cplusplus)
extern "C" {
#endif

extern volatile int g_tv2_sink_int;
extern volatile int g_tv2_source_seed;

#if defined(__cplusplus)
}
#endif

#define TV2_TOUCH_INT(x) do { g_tv2_sink_int ^= (int)(x); } while (0)
