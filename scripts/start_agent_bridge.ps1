# Keep this terminal open while using Continue.
$projectPath = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectPath
& (Join-Path $projectPath '.venv-31210\Scripts\python.exe') -m app.agent_bridge
