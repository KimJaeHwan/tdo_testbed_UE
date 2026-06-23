using UnrealBuildTool;

public class TraceUnrealPlayground : ModuleRules
{
	public TraceUnrealPlayground(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"Engine",
		});

		// 분석 정확도를 위해 케이스 함수가 인라인/제거되지 않도록 한다.
		// (빌드 프로파일 P0/P1 비교는 BuildConfiguration/Target에서 제어)
	}
}
