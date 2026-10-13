[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidatePattern('^\d{8}T\d{6}Z$')][string]$BackupSet,
    [ValidatePattern('^odoo17_restore_drill(_[a-z0-9_]+)?$')][string]$Database = 'odoo17_restore_drill'
)
$ErrorActionPreference = 'Stop'
$Context = 'docker-desktop'
$Contexts = & kubectl config get-contexts -o name
if ($LASTEXITCODE -ne 0 -or $Contexts -notcontains $Context) { throw "Missing '$Context' context." }
$Template = Join-Path $PSScriptRoot 'restore-job.yaml'
$Manifest = & python (Join-Path $PSScriptRoot '../manifest.py') restore --template $Template --backup-set $BackupSet --database $Database
if ($LASTEXITCODE -ne 0) { throw 'Cannot render restore Job.' }
$Manifest | & kubectl --context $Context create -f -
if ($LASTEXITCODE -ne 0) { throw 'Cannot create restore drill Job.' }
$JobName = 'odoo-restore-drill-' + $BackupSet.ToLower()
& kubectl --context $Context -n odoo-system wait --for=condition=complete "job/$JobName" --timeout=900s
$WaitExit = $LASTEXITCODE
& kubectl --context $Context -n odoo-system logs "job/$JobName"
if ($WaitExit -ne 0 -or $LASTEXITCODE -ne 0) { throw 'Restore drill failed; retained database/volume for inspection.' }
