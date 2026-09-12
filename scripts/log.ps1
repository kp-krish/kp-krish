# log.ps1  -  one command to write and push today's engineering log.
#
# Setup once (PowerShell profile):
#   notepad $PROFILE
#   function log { & K:\kp-krish\scripts\log.ps1 @args }
#
# Then from anywhere:
#   log                       -> opens today's note, commits when you close it
#   log "fixed kafka rebalance bug"   -> one-liner, commits immediately

param([string]$Message)

$repo = Split-Path -Parent $PSScriptRoot
$date = Get-Date -Format "yyyy-MM-dd"
$dir  = Join-Path $repo "log\$(Get-Date -Format 'yyyy\\MM')"
$file = Join-Path $dir "$date.md"

New-Item -ItemType Directory -Force -Path $dir | Out-Null

if (-not (Test-Path $file)) {
    @"
# $date

## What I worked on


## What broke / what I learned


## Tomorrow

"@ | Set-Content -Path $file -Encoding UTF8
}

if ($Message) {
    Add-Content -Path $file -Value "- $Message"
} else {
    # Opens in VS Code and waits until you close the tab, then commits.
    code --wait $file
}

Push-Location $repo
git add $file
$staged = git diff --staged --name-only
if ($staged) {
    git commit -m "log($date): $(if ($Message) { $Message } else { 'daily entry' })" | Out-Null
    git push | Out-Null
    Write-Host "pushed $date" -ForegroundColor Green
} else {
    Write-Host "nothing new to commit" -ForegroundColor Yellow
}
Pop-Location