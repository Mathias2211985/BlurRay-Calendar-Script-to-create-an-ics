<#
run_scraper.ps1
Simple PowerShell runner for the bluray-disc scraper.
Usage: start this script from PowerShell (double-clicking the .ps1 in Explorer may not show prompts).
#>

param(
    [string]$Years,
    [string]$Months,
    [string]$OutPattern,
    [string]$CalendarTemplate
)

Set-StrictMode -Version Latest

Push-Location -LiteralPath $PSScriptRoot
try {
    # Prompt interactively if parameters were not provided
    if (-not $Years) {
        $Years = Read-Host "Gib Jahr(e) ein (Komma-getrennt, z.B. 2025 oder 2024,2025) [default: 2025]"
        if ([string]::IsNullOrWhiteSpace($Years)) { $Years = '2025' }
    }
    if (-not $Months) {
        $Months = Read-Host "Gib Monat(e) ein (Komma-getrennt, z.B. 01,02) oder leer für Default-Listings [Enter=leer]"
    }
    if (-not $CalendarTemplate) {
        $CalendarTemplate = Read-Host "Kalender-Template (blu-ray-filme; 3d-blu-ray-filme; 4k-uhd; serien; blu-ray-importe) [oder Enter für Standard]"
        if ([string]::IsNullOrWhiteSpace($CalendarTemplate)) {
            $CalendarTemplate = 'https://bluray-disc.de/4k-uhd/kalender?id={year}-{month:02d}'
        }
    }
    if (-not $OutPattern) {
        $OutPattern = Read-Host "Ausgabe Dateiname Muster (verwende {year} und {months}), z.B. bluray_{year}_{months}.ics [Enter=default]"
        if ([string]::IsNullOrWhiteSpace($OutPattern)) { $OutPattern = 'bluray_{year}_{months}.ics' }
    }

    # Normalize inputs
    $yearList = $Years -split '\s*,\s*' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    if ($Months) { $monthsArg = ($Months -split '\s*,\s*' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }) -join ',' } else { $monthsArg = '' }

    Write-Output "Running scraper for years: $($yearList -join ', ')";
    if ($monthsArg) { Write-Output "Months: $monthsArg" } else { Write-Output "Using default listings (no --months)" }

    $results = @()
    foreach ($y in $yearList) {
        $outName = $OutPattern -replace '\{year\}',$y
        $monthsToken = if ($monthsArg) { $monthsArg -replace ',', '-' } else { 'all' }
        $outName = $outName -replace '\{months\}',$monthsToken

        $args = @()
        $args += '--year'; $args += $y
        if ($monthsArg) {
            $args += '--calendar-template'; $args += $CalendarTemplate
            $args += '--months'; $args += $monthsArg
        }
        $args += '--out'; $args += $outName

        Write-Output "\nStarting: python .\python $($args -join ' ')"
        & python '-u' '.\python' @args
        $exit = $LASTEXITCODE
        $results += [PSCustomObject]@{ Year = $y; Out = $outName; Exit = $exit }
    }

    Write-Output "\nSummary:";
    $results | ForEach-Object { Write-Output "Year=$($_.Year) Out=$($_.Out) Exit=$($_.Exit)" }
    $exitCode = 0
} catch {
    Write-Error "Scraper failed: $_"
    $exitCode = 1
} finally {
    Pop-Location
}

exit $exitCode
