#include "TraceSourcesSinks.h"

static volatile int g_tv2_sink_int    = 0;
static volatile int g_tv2_source_seed = 0x12345678;

extern "C" TV2_NOINLINE int  dfb_source_A() { return g_tv2_source_seed + 1; }
extern "C" TV2_NOINLINE int  dfb_source_B() { return g_tv2_source_seed + 2; }
extern "C" TV2_NOINLINE int  dfb_source_C() { return g_tv2_source_seed + 3; }
extern "C" TV2_NOINLINE void dfb_sink_int(int x) { g_tv2_sink_int ^= x; }
