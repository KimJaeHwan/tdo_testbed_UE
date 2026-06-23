# Testbed V2 — Windows PowerShell 래퍼. build.sh를 Git Bash로 실행한다.
#   .\build.ps1            # all P0
#   .\build.ps1 tier0      # Tier0만
#   .\build.ps1 all P1     # 프로파일 지정
$bash = Join-Path $env:ProgramFiles "Git\bin\bash.exe"
if (-not (Test-Path $bash)) { $bash = "bash" }   # PATH에 있으면 그대로
& $bash "$PSScriptRoot/build.sh" @args
exit $LASTEXITCODE
