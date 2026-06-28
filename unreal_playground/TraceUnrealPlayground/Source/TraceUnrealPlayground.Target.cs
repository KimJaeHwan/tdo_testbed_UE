using UnrealBuildTool;
using System.Collections.Generic;

public class TraceUnrealPlaygroundTarget : TargetRules
{
	public TraceUnrealPlaygroundTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.V2;
		CppStandard = CppStandardVersion.Cpp20;
		IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_1;
		ExtraModuleNames.Add("TraceUnrealPlayground");
	}
}
