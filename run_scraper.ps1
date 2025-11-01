<#
run_scraper.ps1
Simple PowerShell runner for the bluray-disc scraper.
Usage: start this script from PowerShell (double-clicking the .ps1 in Explorer may not show prompts).
#>

param(
    [string]$Years,
    [string]$Months,
    [string]$OutPattern,
    [string]$CalendarTemplate,
    [string]$ReleaseYears,
    [switch]$IgnoreProduction
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
    # Determine ReleaseYears: if provided as parameter, keep; otherwise prompt the user BEFORE building filenames
    if ($PSBoundParameters.ContainsKey('ReleaseYears') -and -not [string]::IsNullOrWhiteSpace($ReleaseYears)) {
        # parameter provided by caller; keep as-is
    } else {
        # Prompt now so the chosen release-years can be embedded into the output filename
        $resp = Read-Host "Gib Release-Jahr(e) ein (Komma-getrennt, z.B. 2025 oder 2024,2025). Leer = ALL"
        if ([string]::IsNullOrWhiteSpace($resp)) { $ReleaseYears = $null } else { $ReleaseYears = $resp }
    }
    # Determine IgnoreProduction: if provided as parameter, keep; otherwise ask the user interactively
    if ($PSBoundParameters.ContainsKey('IgnoreProduction')) {
        # passed on command line; keep as-is
    } else {
        # default to Yes when the user just presses Enter (J/n)
        $resp2 = Read-Host "Ignoriere Produktionsjahr-Prüfung? (J/n)"
        if ([string]::IsNullOrWhiteSpace($resp2)) {
            $IgnoreProduction = $true
        } elseif ($resp2.Trim().ToLower().StartsWith('j')) {
            $IgnoreProduction = $true
        } else {
            $IgnoreProduction = $false
        }
    }
    # Support multiple templates (comma-separated). Convert known slugs to full calendar URLs.
    $templateList = ($CalendarTemplate -split ',') | ForEach-Object { $_.Trim() } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    if (-not $OutPattern) {
        $OutPattern = Read-Host "Ausgabe Dateiname Muster (verwende {year}, {months} und optional {release_years} und {slug}), z.B. bluray_{year}_{months}_{release_years}.ics [Enter=default]"
        if ([string]::IsNullOrWhiteSpace($OutPattern)) { $OutPattern = 'bluray_{year}_{months}.ics' }
    }

    # Normalize inputs
    $yearList = $Years -split '\s*,\s*' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    if ($Months) { $monthsArg = ($Months -split '\s*,\s*' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }) -join ',' } else { $monthsArg = '' }

    Write-Output "Running scraper for years: $($yearList -join ', ')";
    if ($monthsArg) { Write-Output "Months: $monthsArg" } else { Write-Output "Using default listings (no --months)" }
    # show which release-years will be used (or ALL)
    if ([string]::IsNullOrWhiteSpace($ReleaseYears)) { Write-Output "Release-years: ALL" } else { Write-Output "Release-years: $ReleaseYears" }
    Write-Output "Ignore-production: $([bool]$IgnoreProduction)"

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

                # Build the output filename. Support {release_years} token; otherwise we'll ensure the release-years are appended.
                $outName = $OutPattern -replace '\{year\}',$y
                $outName = $outName -replace '\{months\}',$monthsToken

                # prepare a sanitized release-years slug (e.g. '2024-2025' or 'ALL')
                if ([string]::IsNullOrWhiteSpace($ReleaseYears)) {
                    $releaseSlug = 'ALL'
                } else {
                    $releaseSlug = ($ReleaseYears -split '\s*,\s*' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }) -join '-'
                }

                # if pattern contains {release_years}, replace it now
                $releaseIncluded = $false
                if ($outName -match '\{release_years\}') {
                    $outName = $outName -replace '\{release_years\}',$releaseSlug
                    $releaseIncluded = $true
                }

                # replace {slug} if present (we may still append slug later if not present)
                $slugIncluded = $false
                if ($outName -match '\{slug\}') {
                    $outName = $outName -replace '\{slug\}',$slug
                    $slugIncluded = $true
                }

                # ensure release-years are present in the filename (if pattern didn't include them)
                $ext = [IO.Path]::GetExtension($outName)
                if (-not $ext) { $ext = '.ics' }
                $base = if ($ext) { $outName.Substring(0, $outName.Length - $ext.Length) } else { $outName }

                $appendParts = @()
                if (-not $releaseIncluded) { $appendParts += $releaseSlug }
                if (-not $slugIncluded) { $appendParts += $slug }

                if ($appendParts.Count -gt 0) {
                    # avoid duplicating separators
                    $outName = "$base`_$($appendParts -join '_')$ext"
                } else {
                    $outName = "$base$ext"
                }

                $args = @()
                $args += '--year'; $args += $y
                $args += '--calendar-template'; $args += $tplArg
                if ($monthsArg) { $args += '--months'; $args += $monthsArg }
                if ($ReleaseYears) { $args += '--release-years'; $args += $ReleaseYears }
                if ($IgnoreProduction) { $args += '--ignore-production' }
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
