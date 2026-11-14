# Clean installation and exact Version B reproduction

Use Windows PowerShell **5.1** or later, Windows x64 CPython **3.13.7** and uv **0.9.5**.
The package declares Python 3.11–3.13 compatibility; other combinations are not release-verified.
Run from this new source tree, never the original project or dataset. Installation may access
public PyPI. All inference and operational checks are local and require no network.
The [November 3 clarification](OFFICIAL_RULES_CLARIFICATION.md) overrides older upstream advice.

## 1. Fresh locked installation

Choose a NEW tooling directory outside this release and every match-data directory. This keeps
the distributable tree free of environments, caches and build products. Supply absolute local
paths privately. No activation, `py` launcher or untracked helper script is needed.

```powershell
$ErrorActionPreference = 'Stop'
$release = (Get-Location).Path
$python = Read-Host 'Absolute CPython 3.13.7 python.exe path'
$toolsRoot = Read-Host 'Absolute path for a NEW tooling directory outside source and match data'
if (-not [IO.Path]::IsPathRooted($toolsRoot) -or (Test-Path -LiteralPath $toolsRoot)) {
    throw 'Use a new absolute tooling directory'
}
$toolsRoot = [IO.Path]::GetFullPath($toolsRoot)
if ($toolsRoot.TrimEnd('\').StartsWith($release.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Tooling must be outside the source tree'
}
& $python -c 'import sys; assert sys.version_info[:3] == (3, 13, 7) and sys.maxsize > 2**32'
if ($LASTEXITCODE -ne 0) { throw 'Use Windows x64 CPython 3.13.7' }
New-Item -ItemType Directory -Path $toolsRoot | Out-Null
$bootstrap = Join-Path $toolsRoot 'bootstrap'
$environment = Join-Path $toolsRoot 'environment'
& $python -m venv $bootstrap
if ($LASTEXITCODE -ne 0) { throw 'Bootstrap failed' }
& (Join-Path $bootstrap 'Scripts\python.exe') -m pip --isolated install --no-cache-dir --index-url https://pypi.org/simple uv==0.9.5
if ($LASTEXITCODE -ne 0) { throw 'Pinned uv install failed' }
$uv = Join-Path $bootstrap 'Scripts\uv.exe'
$envPython = Join-Path $environment 'Scripts\python.exe'
$savedEnvironment = $env:UV_PROJECT_ENVIRONMENT
$savedCache = $env:UV_CACHE_DIR
try {
    $env:UV_PROJECT_ENVIRONMENT = $environment
    $env:UV_CACHE_DIR = Join-Path $toolsRoot 'uv-cache'
    & $uv sync --locked --extra evaluation --no-config --python $python --no-python-downloads --default-index https://pypi.org/simple --keyring-provider disabled
    if ($LASTEXITCODE -ne 0) { throw 'Locked installation failed' }
    & $uv pip check --python $envPython --no-config --offline
    if ($LASTEXITCODE -ne 0) { throw 'Dependency check failed' }
} finally {
    $env:UV_PROJECT_ENVIRONMENT = $savedEnvironment
    $env:UV_CACHE_DIR = $savedCache
}
```

`pyproject.toml` and `uv.lock` are unchanged. `--locked` rejects inconsistency; do not regenerate
the lock or resolve new versions. A bootstrap environment prevents replacing a running uv.exe
on Windows. Offline installation needs a populated cache; this is not a cold-cache offline claim.
Setuptools may create ignored `src/*.egg-info` during installation; do not include it in publication.

## 2. Synthetic checks

All fixtures are invented. Never put private files in the dedicated test temporary directory;
pytest owns and may replace it. These commands use the variables from step 1.

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONPATH = $null
$env:PYTHONHOME = $null
& $envPython -m pytest -q --basetemp (Join-Path $toolsRoot 'synthetic-pytest') -o ('cache_dir=' + (Join-Path $toolsRoot 'pytest-cache'))
if ($LASTEXITCODE -ne 0) { throw 'Synthetic tests failed' }
$ruff = Join-Path $environment 'Scripts\ruff.exe'
& $ruff check --no-cache src tests scripts
if ($LASTEXITCODE -ne 0) { throw 'Lint failed' }
& $ruff format --check --no-cache src tests scripts
if ($LASTEXITCODE -ne 0) { throw 'Formatting failed' }
```

The suite includes `tests/test_local_temporal.py::test_full_length_temporal_file_pipeline_official_format_and_repeat`:
199,319 invented frames, correct independent halves, unchanged inputs, byte-repeatability and
the unchanged official format validator. It also checks Version A and synthetic scorer compatibility.
No actual possession GT is shipped or read. Upstream files are not reformatted.

## 3. Organizer generation and owner exact-byte gate — LOCAL ONLY

The owner has confirmed this gate passed for the clean Version B release. The procedure remains
available for a future public-clone check; documentation edits do not require changing the model.

For the already accepted B output, use the **same frozen private TOML**, without edits. Do not
copy the public template over it. Retain its input choices, IDs, feature/rule values and
`[inference] mode="rules_temporal"` with the frozen default `[temporal]` settings.
The library's default remains `rules`, so an omitted inference section is not Version B.
`--diagnose` is rule-only and must not be added to the B command.

### A. Organizer generation from licensed inputs

The [public template](version-b.example.toml) now matches the owner-confirmed final B inputs and
non-sensitive settings: tactical TXT/XML only, 199,319 frames, 46 slots, 25 FPS, 105 x 68 m,
radii 1/3/5 m, nearest_k=3, periods `[11185, 90652)` and `[110808, 190198)`,
`rules_temporal`, and no rule/temporal overrides. Homography and Smart Tagging remain absent.
Create a NEW private copy outside public Git. Populate only legitimate input/output paths,
relative TXT/XML names and the correct home/away IDs. Explicit EPTS Score `idLocalTeam` and
`idVisitingTeam` establish orientation; team order and track-slot position do not. Verify
their consistency with team/player references locally. If authoritative role evidence is
missing or inconsistent, stop; do not guess or compare predictions against video.

The schema requires `tag_home` and `tag_away` even though they are unused with Smart Tagging
disabled. In a new organizer config use distinct neutral aliases such as `unused_home` and
`unused_away`; do not use empty strings, N/A, NA or unknown. No Smart Tagging file is needed.
Output root must already exist outside source and dataset. Use local, nonsynced storage.
Do not overwrite or edit the owner's accepted TOML. No owner-private paths/configuration or
accepted CSV are needed to generate predictions. The same licensed input version and correct
local mapping are necessary; comparison with the accepted CSV is a separate exact-byte check.

Run only in the authorized organizer's local terminal, never through hosted AI tools:

```powershell
$organizerConfig = Read-Host 'Absolute path to NEW private organizer Version B TOML'
$organizerOutputRoot = Read-Host 'Existing absolute output_root configured in that TOML'
if (-not [IO.Path]::IsPathRooted($organizerConfig) -or
    -not [IO.Path]::IsPathRooted($organizerOutputRoot) -or
    -not (Test-Path -LiteralPath $organizerConfig -PathType Leaf) -or
    -not (Test-Path -LiteralPath $organizerOutputRoot -PathType Container)) { throw 'Local configuration paths required' }
$organizerRun = 'organizer-b-' + [guid]::NewGuid().ToString('N')
$organizerRunDir = Join-Path $organizerOutputRoot $organizerRun
if (Test-Path -LiteralPath $organizerRunDir) { throw 'Use a fresh run' }
& $envPython -B -m mtah.local --config $organizerConfig --run-name $organizerRun --local-only --verify-repeat *> $null
if ($LASTEXITCODE -ne 0) { throw 'STOP: local inference or repeat verification failed' }
$organizerCsv = Join-Path $organizerRunDir 'submission.csv'
if ((Test-Path -LiteralPath (Join-Path $organizerRunDir '.incomplete')) -or
    -not (Test-Path -LiteralPath $organizerCsv -PathType Leaf)) { throw 'STOP: missing or incomplete new output' }
& $envPython .\evaluation\validate_submission.py $organizerCsv --rows 199319 *> $null
if ($LASTEXITCODE -ne 0) { throw 'STOP: official format validation failed' }
Write-Output 'PASS: ORGANIZER_GENERATION_AND_FORMAT'
```

Keep outputs/diagnostics local. Format and repeat checks do not measure accuracy. Never run
provided-GT evaluation, alter parameters or fabricate labels to resolve an operational failure.

### B. Owner exact-byte reproduction

This gate additionally compares to the already accepted B output. Keep using the same accepted
private TOML. An authorized organizer holding the submitted CSV can also perform that local
comparison; the assistant must not receive the config, CSV or hashes.

From the NEW release, in your own terminal:

```powershell
# Reuse $envPython from installation, or enter its absolute path again.
if (-not (Test-Path variable:envPython)) { $envPython = Read-Host 'New release environment python.exe' }
$privateConfig = Read-Host 'Existing frozen private VERSION B TOML'
$acceptedB = Read-Host 'Previously verified VERSION B CSV (read-only)'
& powershell.exe -NoProfile -File .\scripts\reproduce_version_b.ps1 -Python $envPython -Config $privateConfig -AcceptedCsv $acceptedB
if ($LASTEXITCODE -ne 0) { throw 'STOP RELEASE: exact Version B reproduction did not pass' }
```

The script checks the interpreter/import origin, Phase 1/B mode and frozen temporal defaults.
It creates a **new unique private run directory** under the existing configured output root;
this preserves the exact private config while using a new output directory. It never overwrites
an old run. It runs inference with `--local-only --verify-repeat`, verifies no incomplete marker,
runs the unchanged official validator with `--rows 199319`, and compares SHA-256 against the old
B CSV. It also checks the config/old CSV did not change. No paths, hashes, records or label counts
are printed. All reports remain local. The accepted CSV must be B, not fallback A.

A `STOP` is a release blocker: `preflight` means environment/config/mode/path constraints;
`inference` means runner failure/incompleteness; `official_format` means CSV contract failure;
`exact_bytes` means mismatch; `source_preservation` means an original changed during the run.
Keep incomplete artifacts private and investigate configuration/environment reproducibility.
Never edit labels, alter the selected algorithm, tune parameters, compare with video, or use
provided GT to make the gate pass. Do not send any private artifacts or hashes to the assistant.
Execution policy restrictions must be handled under your normal local policy; no bypass is built in.

## 4. Final submission, only after review and the gate

Complete [the technical report](TECHNICAL_REPORT.md). Review [the release inventory](release-files.txt)
and license authority, then separately approve clean local history and publication of those
source files only to the existing `shefoo21/Ballgorithm-MTAH-2027` repository. Do not inherit
upstream history or use blanket add commands. No publication occurs
in this release task. Record the eventual public revision in the report; none exists yet.

Locally copy the accepted B CSV unchanged to a NEW private `Ballgorithm.csv`, and validate that
exact upload copy with `python evaluation/validate_submission.py <private-copy> --rows 199319`.
Keep validator statistics private. Use `Ballgorithm.md` or `Ballgorithm.pdf` for the technical document.
Submit those two files, the public code URL and registered team name through the emailed form.
The owner-confirmed deadline is **November 17, 2026, 23:59 CET**; the public official
submission document confirms the date. Use the current organizer-emailed form. There is one
response per team and the last pre-deadline edit is scored. Do not upload data or outputs to
the public code repository.


## 5. Proposed clean history and existing repository publication

**PROPOSAL ONLY. Do not run the mutation blocks until the owner explicitly approves them.**
No initialization, staging, commit, remote creation or publication was performed by this audit.
Run in Windows PowerShell 5.1 from the clean release root. Keep all blocks in the same terminal.
Use Git for Windows and [GitHub CLI](https://cli.github.com/) for the guarded commands below.
The November 12 audit did not find `gh` on its shell's PATH; check prerequisites locally.
Installation/authentication is a user action;
never paste credentials into commands or this document. Authenticate only to the approved owner.

The exact proposed Git contents remain [the existing 83-file allowlist](release-files.txt).
Before proceeding, resolve all `OWNER_CONFIRM` fields in the technical report and NOTICE.
Use Ballgorithm as registered. Keep `[FINAL_PUBLIC_GIT_REVISION]` for the standalone upload copy:
a commit cannot contain its own SHA. The source report can explain this convention without a
self-referential follow-up commit. Confirm contribution licensing and public commit identity.

### A. Read-only preflight and explicit local-checkpoint approval

```powershell
$ErrorActionPreference = 'Stop'
$release = (Get-Location).Path.TrimEnd('\')
if ((Split-Path -Leaf $release) -ne 'mtah-2027-version-b-2026-11-12') {
    throw 'Start in the exact clean release root'
}
foreach ($name in @('GIT_DIR','GIT_WORK_TREE','GIT_COMMON_DIR','GIT_INDEX_FILE','GIT_OBJECT_DIRECTORY','GIT_ALTERNATE_OBJECT_DIRECTORIES')) {
    if ([Environment]::GetEnvironmentVariable($name)) { throw 'Use a shell without Git path overrides' }
}
$ancestor = Get-Item -LiteralPath $release
while ($null -ne $ancestor) {
    if (Test-Path -LiteralPath (Join-Path $ancestor.FullName '.git')) {
        throw 'Existing or inherited Git repository: stop; do not reuse history'
    }
    if ($ancestor.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Linked release path' }
    $ancestor = $ancestor.Parent
}
$expected = @(Get-Content -LiteralPath .\docs\release-files.txt)
if ($expected.Count -ne 83 -or @($expected | Sort-Object -Unique).Count -ne 83) { throw 'Allowlist mismatch' }
foreach ($relative in $expected) {
    if ($relative -notmatch '^[A-Za-z0-9_./-]+$' -or $relative -match '(^|/)\.\.(/|$)' -or [IO.Path]::IsPathRooted($relative)) {
        throw 'Unsafe allowlist path'
    }
}
$queue = New-Object 'System.Collections.Generic.Queue[string]'
$queue.Enqueue($release)
$actual = @()
while ($queue.Count -gt 0) {
    foreach ($entry in Get-ChildItem -LiteralPath $queue.Dequeue() -Force) {
        if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Unexpected link/junction' }
        if ($entry.PSIsContainer) { $queue.Enqueue($entry.FullName) } else {
            $actual += $entry.FullName.Substring($release.Length + 1).Replace('\','/')
        }
    }
}
if ($actual.Count -ne 83 -or @(Compare-Object $expected $actual).Count -ne 0) {
    throw 'Extra or missing files: stop for review; do not delete or stage them automatically'
}
$fingerprints = Get-Content -Raw -LiteralPath .\docs\source-fingerprints.json | ConvertFrom-Json
foreach ($property in $fingerprints.sha256.PSObject.Properties) {
    if ($expected -notcontains $property.Name) { throw 'Fingerprint outside allowlist' }
    if ((Get-FileHash -LiteralPath (Join-Path $release $property.Name) -Algorithm SHA256).Hash -ne $property.Value) {
        throw 'Frozen source mismatch: stop without changing the model'
    }
}
$reportText = Get-Content -Raw -LiteralPath .\docs\TECHNICAL_REPORT.md
$noticeText = Get-Content -Raw -LiteralPath .\NOTICE.md
if (($reportText + $noticeText) -match '\[(?:OWNER|USER)_CONFIRM|\[PUBLIC_TEAM_REPOSITORY_URL\]') {
    throw 'Complete the remaining owner-only public report fields first'
}
$publicAuthor = Read-Host 'Approved PUBLIC commit author name'
$publicEmail = Read-Host 'Approved PUBLIC commit email (for example, your GitHub noreply address)'
if ([string]::IsNullOrWhiteSpace($publicAuthor) -or [string]::IsNullOrWhiteSpace($publicEmail)) { throw 'Public identity required' }
if ((Read-Host 'Type APPROVE LOCAL CHECKPOINT after reviewing all 83 public files') -cne 'APPROVE LOCAL CHECKPOINT') {
    throw 'Local checkpoint not approved'
}
```

### B. New local history and exact staging — only after A is approved

```powershell
git init --initial-branch=main --object-format=sha1 '--template='
if ($LASTEXITCODE -ne 0) { throw 'Initialization failed' }
git config --local core.autocrlf false
if ($LASTEXITCODE -ne 0) { throw 'Git configuration failed' }
git config --local core.safecrlf true
if ($LASTEXITCODE -ne 0) { throw 'Git configuration failed' }
git config --local core.whitespace 'blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol'
if ($LASTEXITCODE -ne 0) { throw 'Git whitespace policy failed' }
git config --local core.hooksPath .git/hooks
if ($LASTEXITCODE -ne 0) { throw 'Git configuration failed' }
git config --local user.name $publicAuthor
if ($LASTEXITCODE -ne 0) { throw 'Public identity setup failed' }
git config --local user.email $publicEmail
if ($LASTEXITCODE -ne 0) { throw 'Public identity setup failed' }
$stagedBefore = @(git diff --cached --name-only)
if ($LASTEXITCODE -ne 0 -or $stagedBefore.Count -ne 0) { throw 'Index must be empty' }
git --literal-pathspecs add --pathspec-from-file=docs/release-files.txt
if ($LASTEXITCODE -ne 0) { throw 'Explicit staging failed' }
$staged = @(git diff --cached --name-only)
if ($LASTEXITCODE -ne 0 -or $staged.Count -ne 83 -or @(Compare-Object $expected $staged).Count -ne 0) {
    throw 'Staged contents differ from the approved allowlist'
}
git diff --cached --check
if ($LASTEXITCODE -ne 0) { throw 'Whitespace check failed; do not reformat frozen source' }
$envPython = Read-Host 'Absolute path to the verified release environment python.exe'
$checkStagedBytes = @'
from pathlib import Path
import subprocess
root = Path.cwd()
for name in (root / 'docs/release-files.txt').read_text().splitlines():
    staged = subprocess.check_output(['git', 'show', ':' + name])
    if staged != (root / name).read_bytes():
        raise SystemExit('STOP: Git content conversion; do not commit')
print('All 83 staged blobs match the reviewed source bytes.')
'@
& $envPython -B -c $checkStagedBytes
if ($LASTEXITCODE -ne 0) { throw 'Staged-byte verification failed' }
git diff --cached --stat
if ($LASTEXITCODE -ne 0) { throw 'Staged review failed' }
git --no-pager diff --cached
if ($LASTEXITCODE -ne 0) { throw 'Staged review failed' }
if ((Read-Host 'Type COMMIT BALLGORITHM after reviewing the exact staged diff') -cne 'COMMIT BALLGORITHM') { throw 'Commit not approved' }
git commit -m 'Release Ballgorithm Version B: frozen temporal possession pipeline'
if ($LASTEXITCODE -ne 0) { throw 'Commit failed; stop without resetting or rewriting anything' }
$commit = (git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Cannot read commit' }
$committed = @(git ls-tree -r --name-only HEAD)
if ($LASTEXITCODE -ne 0 -or $committed.Count -ne 83 -or @(Compare-Object $expected $committed).Count -ne 0) { throw 'Commit inventory mismatch' }
$count = git rev-list --count HEAD
if ($LASTEXITCODE -ne 0 -or $count -ne '1') { throw 'Expected one new root commit' }
$rootCommit = git rev-list --max-parents=0 HEAD
if ($LASTEXITCODE -ne 0 -or $rootCommit -ne $commit) { throw 'Inherited history detected' }
$status = @(git status --porcelain=v1 --untracked-files=all)
if ($LASTEXITCODE -ne 0 -or $status.Count -ne 0) { throw 'Working tree is not clean' }
git show -s --format=fuller HEAD
if ($LASTEXITCODE -ne 0) { throw 'Review public commit identity before publication' }
```

The frozen source contains both LF and CRLF files. `core.autocrlf=false` preserves their bytes;
`cr-at-eol` recognizes CRLF as a line ending during whitespace checks. Other whitespace checks
remain active. Do not normalize or reformat the verified source.
The empty Git template avoids inherited hooks; raw staged-byte checks catch line-ending or
global-filter conversion. Never use `git add .`, `git add -A`, force-adds, force pushes, or
history from the original checkout. A failure means stop and review, not reset or delete work.

### C. Existing private repository, reviewed push and separate visibility approval

The exact destination is [shefoo21/Ballgorithm-MTAH-2027](https://github.com/shefoo21/Ballgorithm-MTAH-2027).
It was independently verified PRIVATE and EMPTY in the November 14 read-only review.
Recheck before acting. Do not create a second repository, fork upstream, or import old history.
Sections A/B and separate owner authorization are prerequisites; the documentation-edit approval
does not authorize executing any Git command below. A failed check means stop, not force-push.

```powershell
Get-Command gh -ErrorAction Stop | Out-Null
gh auth status --hostname github.com
if ($LASTEXITCODE -ne 0) { throw 'Authenticate locally with the approved account first' }
$repo = 'shefoo21/Ballgorithm-MTAH-2027'
$publicUrl = 'https://github.com/' + $repo
$remoteJson = gh repo view $repo --json nameWithOwner,visibility,isEmpty,viewerCanAdminister
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect the existing destination' }
$remote = $remoteJson | ConvertFrom-Json
if ($remote.nameWithOwner -cne $repo -or $remote.visibility -ne 'PRIVATE' -or
    -not $remote.isEmpty -or -not $remote.viewerCanAdminister) { throw 'Expected approved private empty repository with admin access' }
$remotes = @(git remote)
if ($LASTEXITCODE -ne 0 -or $remotes.Count -ne 0) { throw 'Unexpected remote; stop for review' }
$status = @(git status --porcelain=v1 --untracked-files=all)
if ($LASTEXITCODE -ne 0 -or $status.Count -ne 0) { throw 'Unreviewed local changes' }
if ((git rev-parse HEAD) -ne $commit) { throw 'Reviewed local revision changed' }
if ((Read-Host 'Type APPROVE PRIVATE SOURCE PUSH for the reviewed 83-file commit') -cne 'APPROVE PRIVATE SOURCE PUSH') {
    throw 'Remote attachment and private push not approved'
}
git remote add origin ($publicUrl + '.git')
if ($LASTEXITCODE -ne 0) { throw 'Remote attachment failed' }
$origin = (git remote get-url origin).Trim()
if ($LASTEXITCODE -ne 0 -or $origin -cne ($publicUrl + '.git')) { throw 'Unexpected push destination' }
$refs = @(git ls-remote origin)
if ($LASTEXITCODE -ne 0 -or $refs.Count -ne 0) { throw 'Remote is no longer empty' }
git push --set-upstream origin main
if ($LASTEXITCODE -ne 0) { throw 'Private push failed; do not force push' }
```

Review the pushed source while the repository is still private. The following uses
[documented GitHub visibility options](https://cli.github.com/manual/gh_repo_edit); the
consequences flag is not a substitute for explicit owner approval.

```powershell
$remoteJson = gh repo view $repo --json nameWithOwner,visibility,defaultBranchRef
if ($LASTEXITCODE -ne 0) { throw 'Cannot verify the private repository' }
$remote = $remoteJson | ConvertFrom-Json
if ($remote.nameWithOwner -cne $repo -or $remote.visibility -ne 'PRIVATE' -or
    $remote.defaultBranchRef.name -ne 'main') { throw 'Unexpected private repository state' }
$remoteHead = @(git ls-remote origin refs/heads/main)
if ($LASTEXITCODE -ne 0 -or $remoteHead.Count -ne 1 -or
    ($remoteHead[0] -split '\s+')[0] -ne $commit) { throw 'Remote revision mismatch' }
$treeJson = gh api "repos/$repo/git/trees/${commit}?recursive=1"
if ($LASTEXITCODE -ne 0) { throw 'Remote inventory unavailable' }
$tree = $treeJson | ConvertFrom-Json
$blobs = @($tree.tree | Where-Object { $_.type -eq 'blob' })
if ($tree.truncated -or $blobs.Count -ne 83 -or
    @(Compare-Object $expected @($blobs.path)).Count -ne 0 -or
    @($tree.tree | Where-Object { $_.type -eq 'commit' -or $_.mode -eq '120000' }).Count -ne 0) { throw 'Unexpected remote contents' }
if ((Read-Host 'Type MAKE REVIEWED BALLGORITHM PUBLIC after reviewing private repository contents and visibility consequences') -cne 'MAKE REVIEWED BALLGORITHM PUBLIC') {
    throw 'Public visibility not approved'
}
gh repo edit $repo --visibility public --accept-visibility-change-consequences
if ($LASTEXITCODE -ne 0) { throw 'Visibility change failed; inspect state before any retry' }
```

If GitHub CLI is unavailable, stop these blocks. Any browser alternative must use this
existing repository, preserve the same inventory/revision checks and obtain the same separate
approvals. Do not use GitHub's New repository page or upload a checkout archive.

### D. Public visibility, inventory and reproducibility checks

```powershell
$publishedJson = gh repo view $repo --json nameWithOwner,visibility,defaultBranchRef,url
if ($LASTEXITCODE -ne 0) { throw 'Cannot verify public repository' }
$published = $publishedJson | ConvertFrom-Json
if ($published.visibility -ne 'PUBLIC' -or $published.nameWithOwner -ine $repo -or $published.defaultBranchRef.name -ne 'main') { throw 'Public repository settings mismatch' }
$remoteHead = @(git ls-remote origin refs/heads/main)
if ($LASTEXITCODE -ne 0 -or $remoteHead.Count -ne 1 -or ($remoteHead[0] -split '\s+')[0] -ne $commit) { throw 'Published revision mismatch' }
$treeJson = gh api "repos/$repo/git/trees/${commit}?recursive=1"
if ($LASTEXITCODE -ne 0) { throw 'Cannot verify published inventory' }
$tree = $treeJson | ConvertFrom-Json
if ($tree.truncated) { throw 'Incomplete remote inventory' }
$blobs = @($tree.tree | Where-Object { $_.type -eq 'blob' })
if ($blobs.Count -ne 83 -or @(Compare-Object $expected @($blobs.path)).Count -ne 0 -or
    @($tree.tree | Where-Object { $_.type -eq 'commit' -or $_.mode -eq '120000' }).Count -ne 0) { throw 'Unexpected remote contents' }
$cloneRoot = Read-Host 'NEW absolute public-clone directory outside all dataset/private-output directories'
if (-not [IO.Path]::IsPathRooted($cloneRoot) -or (Test-Path -LiteralPath $cloneRoot)) { throw 'Use a new clone directory' }
git -c core.autocrlf=false clone --config core.autocrlf=false --single-branch --branch main -- $publicUrl $cloneRoot
if ($LASTEXITCODE -ne 0) { throw 'Clean public clone failed' }
if ((git -C $cloneRoot rev-parse HEAD) -ne $commit) { throw 'Clone revision mismatch' }
foreach ($relative in $expected) {
    if ((Get-FileHash -LiteralPath (Join-Path $cloneRoot $relative) -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath (Join-Path $release $relative) -Algorithm SHA256).Hash) { throw 'Clone byte mismatch' }
}
Write-Output 'Published source inventory and public-clone bytes match the approved release.'
```

Open the URL while signed out and inspect its file tree, README links and technical report.
If a separately reviewed browser route is used, retain the same clone/hash checks and
independently verify visibility and contents. Then install a **new** locked environment from that
clone
(sections 1–2), and independently run section 3 using the same frozen private B configuration
and accepted CSV. Keep all private processing in your own terminal. Stop on any mismatch; do
not tune, refit, relabel or inspect predictions against video. Record the actual public revision
only in the standalone technical upload copy, not by trying to embed a commit's own SHA.

## 6. Exact Ballgorithm upload preparation — USER ONLY

Do this locally after the public-source checks. The assistant never opens these files. Keep
the original accepted B CSV immutable. Do not open/resave it through a spreadsheet editor.
The following creates a fresh private staging folder and copies bytes without overwriting.
Use the legitimate dataset-root location solely to prevent accidentally writing inside it.

```powershell
$ErrorActionPreference = 'Stop'
$envPython = Read-Host 'Verified environment python.exe (with evaluation extra)'
$acceptedB = Read-Host 'Existing verified Version B CSV'
$inputRoot = (Resolve-Path -LiteralPath (Read-Host 'Original dataset root, for output-location guard only')).Path.TrimEnd('\')
$uploadParent = (Resolve-Path -LiteralPath (Read-Host 'Existing private upload parent outside source and dataset')).Path.TrimEnd('\')
foreach ($forbidden in @($inputRoot, $release, $cloneRoot)) {
    if ($forbidden -and ($uploadParent -ieq $forbidden -or $uploadParent.StartsWith($forbidden.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase))) { throw 'Unsafe staging location' }
}
$uploadDir = Join-Path $uploadParent ('Ballgorithm-upload-' + [guid]::NewGuid().ToString('N'))
if (Test-Path -LiteralPath $uploadDir) { throw 'Never overwrite an existing staging folder' }
New-Item -ItemType Directory -Path $uploadDir | Out-Null
$csvUpload = Join-Path $uploadDir 'Ballgorithm.csv'
$originalHash = (Get-FileHash -LiteralPath $acceptedB -Algorithm SHA256).Hash
[IO.File]::Copy($acceptedB, $csvUpload, $false)
& $envPython (Join-Path $release 'evaluation\validate_submission.py') $csvUpload --rows 199319 *> $null
if ($LASTEXITCODE -ne 0) { throw 'STOP: exact upload copy failed official format validation' }
if ((Get-FileHash -LiteralPath $csvUpload -Algorithm SHA256).Hash -ne $originalHash -or
    (Get-FileHash -LiteralPath $acceptedB -Algorithm SHA256).Hash -ne $originalHash) { throw 'STOP: byte mismatch or original changed' }
if ($commit -notmatch '^[0-9a-f]{40}$') { throw 'Actual approved public Git revision required' }
$reportUpload = Join-Path $uploadDir 'Ballgorithm.md'
$text = [IO.File]::ReadAllText((Join-Path $release 'docs\TECHNICAL_REPORT.md'))
$text = $text.Replace('[FINAL_PUBLIC_GIT_REVISION]', ('[' + $commit + '](' + $publicUrl + '/commit/' + $commit + ')'))
$text = $text.Replace('(publication pending; verified private and empty on November 14, 2026).', '(public; exact revision linked below).')
$text = [regex]::Replace($text, '(?ms)^> Complete bracketed fields locally.*?(?=^\*\*Team:\*\*)', '')
$reportLinks = @{
    'ARCHITECTURE.md' = 'docs/ARCHITECTURE.md'
    'REPRODUCE.md' = 'docs/REPRODUCE.md'
    'RELEASE_VERIFICATION.md' = 'docs/RELEASE_VERIFICATION.md'
    '../NOTICE.md' = 'NOTICE.md'
}
foreach ($relative in $reportLinks.Keys) {
    $text = $text.Replace(('](' + $relative + ')'), ('](' + $publicUrl + '/blob/' + $commit + '/' + $reportLinks[$relative] + ')'))
}
if ($text -match '\[(?:OWNER|USER)_CONFIRM|\[PUBLIC_TEAM_REPOSITORY_URL\]|\[FINAL_PUBLIC') { throw 'Complete owner-only report fields before upload' }
if (Test-Path -LiteralPath $reportUpload) { throw 'Never overwrite an existing report' }
[IO.File]::WriteAllText($reportUpload, $text, (New-Object Text.UTF8Encoding($false)))
Write-Output 'Private Ballgorithm.csv copy validated and unchanged; complete the final document review locally.'
```

Review the separate `Ballgorithm.md`: the block removes the completion note, fills the actual
revision and rewrites its four local document links to absolute URLs pinned to that commit.
Confirm every link resolves publicly and no owner marker or private detail remains. Keep this
upload copy outside the release and the 83-file allowlist. It is created only after the public
commit exists; no self-referential source commit or extra release file is needed.
Verify the confirmed team spelling, enabled inputs, non-sensitive settings, provenance and
revision. If converting to PDF, name it **Ballgorithm.pdf** and inspect the rendered pages and
links locally; Markdown is accepted and avoids conversion requirements. Do not attach private
configs, hashes, manifests, match statistics or reports. Do not edit `Ballgorithm.csv`.

Finally use the form emailed to registered participants. Supply **Ballgorithm**, **Ballgorithm.csv**,
the public team repository URL, and **Ballgorithm.md** or **Ballgorithm.pdf**. Confirm the cutoff
timezone in the organizer's email and submit before **November 17, 2026**. Verify the received
files/URL and retain the form confirmation privately. Only one team response is needed; the last
pre-deadline edit is scored. No form URL or submission receipt has been invented here.
[Official submission requirements](https://github.com/metrica-sports/more-than-a-hack-2027/blob/main/SUBMISSION.md).
