#include "tv2_sources_sinks.h"

volatile int g_tv2_sink_int    = 0;
volatile int g_tv2_source_seed = 0x12345678;

TV2_SOURCE int dfb_source_A(void) { return g_tv2_source_seed + 1; }
TV2_SOURCE int dfb_source_B(void) { return g_tv2_source_seed + 2; }
TV2_SOURCE int dfb_source_C(void) { return g_tv2_source_seed + 3; }

TV2_SINK void dfb_sink_int(int x) { TV2_TOUCH_INT(x); }
