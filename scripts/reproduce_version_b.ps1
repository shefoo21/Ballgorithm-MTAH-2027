#requires -Version 5.1
# Run only in the user's local terminal. No report contents or hashes are printed.
param(
    [Parameter(Mandatory=$true)][string]$Python,
    [Parameter(Mandatory=$true)][string]$Config,
    [Parameter(Mandatory=$true)][string]$AcceptedCsv
)
$ErrorActionPreference = 'Stop'
$stage = 'preflight'
$oldBytecode = $env:PYTHONDONTWRITEBYTECODE
$oldPythonPath = $env:PYTHONPATH
$oldPythonHome = $env:PYTHONHOME
$release = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $release
try {
    # Explicit system module avoids a PowerShell 7 PSModulePath inherited through Python.
    Import-Module ([IO.Path]::Combine($PSHOME, 'Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1')) -ErrorAction Stop
    $env:PYTHONDONTWRITEBYTECODE = '1'
    $env:PYTHONPATH = $null
    $env:PYTHONHOME = $null
    # Explicit interpreter, private configuration and previous CSV are read-only.
    $beforeConfig = (Get-FileHash -LiteralPath $Config -Algorithm SHA256).Hash
    $beforeCsv = (Get-FileHash -LiteralPath $AcceptedCsv -Algorithm SHA256).Hash
    $preflight = @'
import sys
from pathlib import Path
try:
    import mtah
    from mtah.local.config import load_local_config
    from mtah.inference.temporal import TemporalConfig
    root = Path.cwd().resolve()
    assert sys.version_info[:3] == (3, 13, 7)
    assert Path(mtah.__file__).resolve().is_relative_to(root / 'src')
    assert not Path(sys.argv[1]).resolve().is_relative_to(root)
    assert not Path(sys.argv[2]).resolve().is_relative_to(root)
    c = load_local_config(sys.argv[1])
    assert c.profile == 'phase1' and c.frame_count == 199319
    assert c.mode == 'rules_temporal' and c.temporal == TemporalConfig()
    assert not c.output_root.is_relative_to(root)
    assert not root.is_relative_to(c.output_root)
    assert not root.is_relative_to(c.dataset_root)
    print(c.output_root)
except (Exception, KeyboardInterrupt):
    sys.exit(1)
'@
    $outputLines = @(& $Python -c $preflight $Config $AcceptedCsv 2>$null)
    if ($LASTEXITCODE -ne 0 -or $outputLines.Count -ne 1) { throw 'preflight' }
    $runName = 'release-b-' + [guid]::NewGuid().ToString('N')
    $newRun = Join-Path $outputLines[0] $runName
    if (Test-Path -LiteralPath $newRun) { throw 'existing_run' }
    $stage = 'inference'
    & $Python -m mtah.local --config $Config --run-name $runName --local-only --verify-repeat *> $null
    if ($LASTEXITCODE -ne 0) { throw 'inference' }
    $newCsv = Join-Path $newRun 'submission.csv'
    if ((Test-Path -LiteralPath (Join-Path $newRun '.incomplete')) -or
        -not (Test-Path -LiteralPath $newCsv -PathType Leaf)) { throw 'incomplete' }
    $stage = 'official_format'
    & $Python .\evaluation\validate_submission.py $newCsv --rows 199319 *> $null
    if ($LASTEXITCODE -ne 0) { throw 'official_format' }
    $stage = 'exact_bytes'
    if ((Get-FileHash -LiteralPath $newCsv -Algorithm SHA256).Hash -ne $beforeCsv) { throw 'mismatch' }
    $stage = 'source_preservation'
    if ((Get-FileHash -LiteralPath $Config -Algorithm SHA256).Hash -ne $beforeConfig -or
        (Get-FileHash -LiteralPath $AcceptedCsv -Algorithm SHA256).Hash -ne $beforeCsv) { throw 'changed' }
    Write-Output 'PASS: Version B repeat, official 199319-row format and exact-byte reproduction.'
    Write-Output 'Keep the new run and all private material local. Publication is a separate review.'
    exit 0
} catch {
    Write-Output ('STOP: release_gate/' + $stage + '. Preserve all runs; do not change parameters.')
    exit 1
} finally {
    Pop-Location
    $env:PYTHONDONTWRITEBYTECODE = $oldBytecode
    $env:PYTHONPATH = $oldPythonPath
    $env:PYTHONHOME = $oldPythonHome
}
