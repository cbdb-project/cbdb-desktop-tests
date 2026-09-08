# run_tests.ps1 -- the one command that produces a complete build report.
#
#   .\run_tests.ps1              stage, test, report
#   .\run_tests.ps1 -Restage     discard the cached tree and unpack again
#   .\run_tests.ps1 -Fast        skip everything that needs the running app
#   .\run_tests.ps1 -Filter x    pass -k x to pytest
#   .\run_tests.ps1 -DryRun      print the commands, run nothing
#
# Every step is automated: there is no manual gate, and the script fails
# loudly rather than leaving reports/ half-written.  A test failure does
# not stop the report -- a run that found something is exactly the run
# worth reporting on -- but it does decide the exit code, so CI still
# sees red.

param(
    [switch]$Restage,
    [switch]$Fast,
    [switch]$DryRun,
    [string]$Filter = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Several steps print Chinese names; on a legacy console codepage that
# raises UnicodeEncodeError and would silently truncate a report.
$env:PYTHONIOENCODING = "utf-8"

$ROOT = $PSScriptRoot
$STAMP = Get-Date -Format "yyyyMMdd-HHmmss"
$REPORTS = Join-Path $ROOT "reports"
$JSON = Join-Path $REPORTS "pytest_report.json"
$ARCHIVE = Join-Path $REPORTS "runs"

function Step($label) {
    Write-Host ""
    Write-Host "=== $label" -ForegroundColor Cyan
}

function Run($command) {
    if ($DryRun) { Write-Host "[dry-run] $command"; return 0 }
    Write-Host "> $command" -ForegroundColor DarkGray
    # Out-Host, not the pipeline: anything the command prints would
    # otherwise be returned alongside the exit code, and "$code -ne 0"
    # would then compare an array and always be true.
    Invoke-Expression $command | Out-Host
    return $LASTEXITCODE
}

# ---- 0. preflight ---------------------------------------------------------
Step "Checking the environment"
if (-not (Test-Path (Join-Path $ROOT ".env"))) {
    throw ".env not found.  Copy .env.example to .env and point CBDB_DESKTOP_ZIP at the distribution you want to test."
}
if ($DryRun) {
    Write-Host "[dry-run] python -c 'import pytest, requests'"
} else {
    # The browser tests skip themselves when Playwright has no Chromium,
    # which is the right behaviour and also easy to miss in a run's
    # output -- so say so here, before the run, where it is read.
    $browserWhy = python -c "import sys; sys.path.insert(0,'tests'); from cbdb_desktop import browser; ok, why = browser.available(); print('' if ok else why)" 2>$null
    if ($browserWhy) {
        Write-Host "  browser tests will SKIP: $browserWhy" -ForegroundColor Yellow
    } else {
        Write-Host "  browser tests enabled (Playwright Chromium found)" -ForegroundColor DarkGray
    }

    python -c "import pytest, requests, pytest_jsonreport" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "missing dependencies.  Run: python -m pip install -r requirements.txt"
    }
}

# ---- 1. keep the previous run -------------------------------------------
# Copied, not moved.  Moving the current report aside before the new run
# has produced one leaves the repository with no report at all if staging
# or pytest then fails -- and the report is the deliverable.
Step "Archiving the previous run"
New-Item -ItemType Directory -Force -Path $ARCHIVE | Out-Null
foreach ($name in @("pytest_report.json",
                    "CBDB_Desktop_Issues_EN.md",
                    "CBDB_Desktop_Issues_ZH-Hant.md")) {
    $previous = Join-Path $REPORTS $name
    if (Test-Path $previous) {
        $kept = Join-Path $ARCHIVE ("{0}-{1}" -f $STAMP, $name)
        if ($DryRun) {
            Write-Host "[dry-run] copy $previous -> $kept"
        } else {
            Copy-Item $previous $kept
            Write-Host "  kept $kept"
        }
    }
}

# ---- 2. stage the distribution -------------------------------------------
Step "Staging the distribution"
$stageArgs = if ($Restage) { "--force" } else { "" }
$code = Run "python `"$ROOT\stage.py`" $stageArgs"
if ($code -ne 0) { throw "staging failed" }

# ---- 3. run the tests ----------------------------------------------------
Step "Running the tests"
$pytestArgs = @("`"$ROOT\tests`"", "-q", "--json-report",
                "--json-report-file=`"$JSON`"")
# Deliberately NOT --restage: step 2 above already forced a fresh unpack,
# in its own process, and pytest cannot know that.  Passing it here made
# the run re-extract 1.3 GB a second time and then rename the tree the
# first pass had just installed -- which Windows refused mid-swap with
# PermissionError [WinError 5], erroring all 678 tests.  One restage per
# run is a restage.
if ($Restage) { $pytestArgs += "--refresh-inputs" }
if ($Fast)    { $pytestArgs += @("-m", "`"not app`"") }
if ($Filter)  { $pytestArgs += @("-k", "`"$Filter`"") }

$testCode = Run ("python -m pytest " + ($pytestArgs -join " "))

# ---- 4. write the reports ------------------------------------------------
# English and Traditional Chinese, each as Markdown, Word and PDF.
Step "Writing the issue reports"
if ($Fast) {
    Write-Host "  skipped: -Fast leaves out the app tests, so the report would say nothing about the build" -ForegroundColor Yellow
} else {
    $code = Run "python `"$ROOT\reports\generate_report.py`""
    # A missing Word installation costs the .pdf, not the run: the
    # generator still writes .md and .docx and says what it could not do.
    if ($code -ne 0) {
        Write-Host "  some report formats could not be written (see above)" -ForegroundColor Yellow
    }
}

# ---- 5. say what happened ------------------------------------------------
Step "Summary"
if (-not $DryRun -and -not $Fast) {
    if (-not (Test-Path $JSON)) { throw "no JSON report was produced" }
    $report = Get-Content $JSON -Raw | ConvertFrom-Json
    $s = $report.summary
    # The JSON omits an outcome entirely when its count is zero, and
    # StrictMode makes reading an absent property fatal.
    function Count($name) {
        if ($s.PSObject.Properties.Name -contains $name) { return $s.$name }
        return 0
    }
    Write-Host ("  {0} passed, {1} xfailed, {2} skipped, {3} failed, {4} error(s)" -f `
        (Count "passed"), (Count "xfailed"), (Count "skipped"), (Count "failed"), (Count "error"))
    Write-Host ("  issue reports: {0}" -f (Join-Path $REPORTS "CBDB_Desktop_Issues_EN.*"))
    Write-Host ("                 {0}" -f (Join-Path $REPORTS "CBDB_Desktop_Issues_ZH-Hant.*"))

    if ((Count "xpassed") -gt 0) {
        Write-Host ("  {0} test(s) passed unexpectedly: a recorded defect may have been fixed." -f (Count "xpassed")) -ForegroundColor Yellow
        Write-Host "  Check the issues report and remove that defect's xfail marker." -ForegroundColor Yellow
    }
}

if ($testCode -ne 0) {
    Write-Host ""
    Write-Host "Tests reported failures; the report above covers this run." -ForegroundColor Yellow
}
exit $testCode
