param([string]$HtmlDir, [switch]$AllowPartial)
$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'
$runArguments = @((Join-Path $PSScriptRoot 'main.py'), 'all')
if ($HtmlDir) { $runArguments += @('--html-dir', $HtmlDir) }
if ($AllowPartial) { $runArguments += '--allow-partial' }
python @runArguments
exit $LASTEXITCODE
