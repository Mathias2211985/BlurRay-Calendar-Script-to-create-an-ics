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
        $CalendarTemplate = Read-Host "Kalender-Template (Komma-getrennt: blu-ray-filme,3d-blu-ray-filme,4k-uhd,serien,blu-ray-importe) oder volle URL/Segment (z.B. {year}-{month:02d}) [Enter=Standard (4k-uhd)]"
        if ([string]::IsNullOrWhiteSpace($CalendarTemplate)) {
            $CalendarTemplate = '4k-uhd'
        }
    }
    # Support multiple templates (comma-separated). Convert known slugs to full calendar URLs.
    $templateList = ($CalendarTemplate -split ',') | ForEach-Object { $_.Trim() } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
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
        $monthsToken = if ($monthsArg) { $monthsArg -replace ',', '-' } else { 'all' }

        foreach ($tpl in $templateList) {
                # determine template argument (URL) from common slugs, full URLs or embedded segments
                $tplLower = $tpl.ToLower()
                if ($tplLower -match '^(blu-ray-filme|3d-blu-ray-filme|4k-uhd|serien|blu-ray-importe)$') {
                    $tplArg = "https://bluray-disc.de/$tplLower/kalender?id={year}-{month:02d}"
                } elseif ($tplLower -match '^(https?://)') {
                    $tplArg = $tpl
                } elseif ($tpl -match '\{year' -or $tpl -match '\{month') {
                    # segment containing placeholders, embed into canonical calendar_template path
                    $tplArg = "https://bluray-disc.de/calendar_template/kalender?id={$tpl}"
                } else {
                    # assume it's a slug-like value
                    $tplArg = "https://bluray-disc.de/$tplLower/kalender?id={year}-{month:02d}"
                }

                # derive a safe slug for filename disambiguation from the original template token
                $slugRaw = $tpl
                # if it's a full URL, try to extract a meaningful segment like '/<slug>/kalender'
                if ($slugRaw -match 'https?://[^/]+/([^/]+)/kalender') { $slugRaw = $matches[1] }
                # if it contains an id=... parameter, try to use that
                elseif ($slugRaw -match 'id=([^&]+)') { $slugRaw = $matches[1] }

                # sanitize into a filename-safe slug (lowercase, keep a-z0-9._-)
                $slug = $slugRaw.ToLower() -replace '[^a-z0-9\-_.]', '-' -replace '-{2,}', '-' -replace '(^-+|-+$)',''
                if ([string]::IsNullOrWhiteSpace($slug)) { $slug = 'tpl' }

                # Build the output filename. If user provided {slug} in OutPattern, replace it.
                # Otherwise append _{slug} before the extension to avoid overwrites across templates.
                $outName = $OutPattern -replace '\{year\}',$y
                $outName = $outName -replace '\{months\}',$monthsToken
                if ($outName -match '\{slug\}') {
                    $outName = $outName -replace '\{slug\}',$slug
                } else {
                    # append slug before extension
                    $ext = [IO.Path]::GetExtension($outName)
                    if (-not $ext) { $ext = '.ics' }
                    $base = if ($ext) { $outName.Substring(0, $outName.Length - $ext.Length) } else { $outName }
                    $outName = "$base`_$slug$ext"
                }

                $args = @()
                $args += '--year'; $args += $y
                $args += '--calendar-template'; $args += $tplArg
                if ($monthsArg) { $args += '--months'; $args += $monthsArg }
                $args += '--out'; $args += $outName

            Write-Output "\nStarting: python .\python $($args -join ' ')"
            & python '-u' '.\python' @args
            $exit = $LASTEXITCODE
            $results += [PSCustomObject]@{ Year = $y; Template = $tplArg; Out = $outName; Exit = $exit }
        }
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
