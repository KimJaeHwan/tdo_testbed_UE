using UnrealBuildTool;
using System.Collections.Generic;

public class TraceUnrealPlaygroundEditorTarget : TargetRules
{
	public TraceUnrealPlaygroundEditorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Editor;
		bOverrideBuildEnvironment = true;
		DefaultBuildSettings = BuildSettingsVersion.V2;
		CppStandard = CppStandardVersion.Cpp20;
		IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_1;
		ExtraModuleNames.Add("TraceUnrealPlayground");
	}
}
