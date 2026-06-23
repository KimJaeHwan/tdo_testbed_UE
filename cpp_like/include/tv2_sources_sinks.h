#pragma once
#include "tv2.h"

/* DataFlowBench 호환 source/sink 경계.
 * core 엔진은 이 이름을 모르며, DataFlowBenchBoundaryBinder가 경계로 인식한다. */

TV2_EXTERN_C TV2_SOURCE int  dfb_source_A(void);
TV2_EXTERN_C TV2_SOURCE int  dfb_source_B(void);
TV2_EXTERN_C TV2_SOURCE int  dfb_source_C(void);

TV2_EXTERN_C TV2_SINK   void dfb_sink_int(int x);
