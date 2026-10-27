$projectPath = Split-Path -Parent $PSScriptRoot
& python (Join-Path $projectPath 'scripts/portable.py') bridge @args
exit $LASTEXITCODE
