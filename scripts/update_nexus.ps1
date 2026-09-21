param(
    [switch]$NoGit,
    [switch]$SkipHistory,
    [switch]$SkipTraining
)

$ErrorActionPreference = "Stop"
$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Repo
$LogPath = Join-Path $Repo "update_nexus.log"

function Log([string]$Message) {
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $LogPath -Value "[$stamp] $Message" -Encoding UTF8
}

function Fail([string]$Message) {
    Write-Host ""
    Write-Host "[ERROR] $Message" -ForegroundColor Red
    Log "ERROR: $Message"
    throw $Message
}

function RepoPath([string]$p) {
    return [System.IO.Path]::GetFullPath((Join-Path $Repo $p))
}

function Find-Latest([string[]]$Patterns) {
    $dir = RepoPath $Cfg.inbox_dir
    if (!(Test-Path $dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }
    $items = @()
    foreach ($pat in $Patterns) {
        $items += Get-ChildItem -Path $dir -Filter $pat -File -ErrorAction SilentlyContinue
    }
    return $items | Sort-Object LastWriteTime -Descending | Select-Object -First 1
}

function Run {
    param(
        [Parameter(Mandatory=$true)][string]$Exe,
        [Parameter(Mandatory=$false)][string[]]$CmdArgs = @()
    )
    $line = "> $Exe $($CmdArgs -join ' ')"
    Write-Host $line -ForegroundColor DarkGray
    Log $line
    & $Exe @CmdArgs
    $rc = $LASTEXITCODE
    if ($null -eq $rc) { $rc = 0 }
    if ($rc -ne 0) {
        Fail "$Exe failed (exit=$rc)"
    }
}

$script:PythonExe = $null
$script:PythonPrefix = @()

function Resolve-Python {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($null -ne $py) {
        $script:PythonExe = "py"
        $script:PythonPrefix = @("-3")
        return
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($null -ne $python) {
        $script:PythonExe = "python"
        $script:PythonPrefix = @()
        return
    }

    Fail "Python が見つかりません。Git Bashで python --version または py -3 --version を確認してください。"
}

function Run-Python {
    param(
        [Parameter(Mandatory=$false)][string[]]$PyArgs = @()
    )
    [string[]]$allArgs = @()
    $allArgs += $script:PythonPrefix
    $allArgs += $PyArgs
    Run -Exe $script:PythonExe -CmdArgs $allArgs
}

function Paste-CsvToSheet(
    $Excel,
    $Book,
    [string]$CsvPath,
    [string]$SheetName,
    [int]$ExpectedCols
) {
    Write-Host "  paste: $([System.IO.Path]::GetFileName($CsvPath)) -> $SheetName" -ForegroundColor Cyan
    Log "paste: $CsvPath -> $SheetName"

    $sheet = $Book.Worksheets.Item($SheetName)
    $csvBook = $Excel.Workbooks.Open($CsvPath)

    try {
        $src = $csvBook.Worksheets.Item(1).UsedRange
        $rows = [int]$src.Rows.Count
        $cols = [int]$src.Columns.Count

        if ($cols -ne $ExpectedCols) {
            Fail "$SheetName : CSV列数=$cols / 想定=$ExpectedCols"
        }

        $clearRows = [Math]::Max([int]$sheet.UsedRange.Rows.Count, $rows)
        $null = $sheet.Range(
            $sheet.Cells.Item(1,1),
            $sheet.Cells.Item($clearRows,$ExpectedCols)
        ).ClearContents()

        $dest = $sheet.Range(
            $sheet.Cells.Item(1,1),
            $sheet.Cells.Item($rows,$cols)
        )
        $dest.Value2 = $src.Value2

        # Emit only the row count from this function.
        Write-Output ([int]$rows)
        return
    }
    finally {
        $csvBook.Close($false)
    }
}

try {
    Log "=============================================="
    Log "Runaway's Nexus update start"
    Log "Repo=$Repo"

    Write-Host "=== Runaway's Nexus Data Update V9 ===" -ForegroundColor Green
    Write-Host "Repo: $Repo"
    Write-Host "Log : $LogPath"
    Write-Host ""

    # ---------- PRE-FLIGHT ----------
    Write-Host "[PRE-FLIGHT] 環境確認" -ForegroundColor Yellow

    if (!(Test-Path (Join-Path $Repo ".git"))) {
        Fail "ここはGitリポジトリ直下ではありません。nexus_auto_update の中身を Runaways-Nexus 直下へコピーしてください。"
    }

    $ConfigPath = Join-Path $Repo "config/data_update.json"
    if (!(Test-Path $ConfigPath)) {
        Fail "config/data_update.json が見つかりません。"
    }

    $Cfg = Get-Content $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json

    Resolve-Python
    Write-Host "  Python: $script:PythonExe $($script:PythonPrefix -join ' ')" -ForegroundColor Green
    Log "Python=$script:PythonExe $($script:PythonPrefix -join ' ')"

    Run-Python -PyArgs @("-c", "import pandas, openpyxl; print('  pandas/openpyxl: OK')")

    if (-not $SkipTraining) {
        $template = RepoPath $Cfg.training_template
        if (!(Test-Path $template)) {
            Fail "調教判定表テンプレートがありません: $template"
        }

        try {
            $excelTest = New-Object -ComObject Excel.Application
            $excelVersion = $excelTest.Version
            $excelTest.Quit()
            [System.Runtime.Interopservices.Marshal]::ReleaseComObject($excelTest) | Out-Null
            Write-Host "  Microsoft Excel COM: OK (Version $excelVersion)" -ForegroundColor Green
            Log "Excel COM OK version=$excelVersion"
        }
        catch {
            Fail "Microsoft ExcelをCOMから起動できません。Windows版Excelのインストールを確認してください。詳細: $($_.Exception.Message)"
        }
    }

    # Input files before doing any update.
    $de = Find-Latest $Cfg.de_patterns
    $hill = Find-Latest $Cfg.hill_patterns
    $wood = Find-Latest $Cfg.wood_patterns
    $horse = Find-Latest $Cfg.horse_patterns
    $race = Find-Latest $Cfg.race_patterns

    Write-Host ""
    Write-Host "  data/inbox 検出結果:" -ForegroundColor Cyan
    Write-Host "    DE       : $($de.Name)"
    Write-Host "    h        : $($hill.Name)"
    Write-Host "    w        : $($wood.Name)"
    Write-Host "    馬単位   : $($horse.Name)"
    Write-Host "    レース   : $($race.Name)"

    if (-not $SkipTraining) {
        if ($null -eq $de)   { Fail "DE*.CSV が data/inbox にありません。" }
        if ($null -eq $hill) { Fail "h.csv が data/inbox にありません。" }
        if ($null -eq $wood) { Fail "w.csv が data/inbox にありません。" }
    }

    if (-not $SkipHistory) {
        if ($null -eq $horse) { Fail "馬単位*.csv が data/inbox にありません。" }
        if ($null -eq $race)  { Fail "レースデータ*.csv が data/inbox にありません。" }
    }

    # ---------- UPDATE ----------
    if (-not $NoGit) {
        Write-Host ""
        Write-Host "[0/6] Git pull --rebase --autostash" -ForegroundColor Yellow
        Run -Exe "git" -CmdArgs @("pull","--rebase","--autostash",$Cfg.git_remote,$Cfg.git_branch)
    }

    if (-not $SkipTraining) {
        Write-Host ""
        Write-Host "[1/6] 調教判定表へ DE/h/w を自動貼付して再計算" -ForegroundColor Yellow

        $template = RepoPath $Cfg.training_template
        $working = RepoPath $Cfg.training_workbook_latest
        $rawExport = RepoPath $Cfg.training_raw_export

        New-Item -ItemType Directory -Force -Path ([System.IO.Path]::GetDirectoryName($working)) | Out-Null
        Copy-Item $template $working -Force

        $excel = $null
        $book = $null

        try {
            $excel = New-Object -ComObject Excel.Application
            $excel.Visible = $false
            $excel.DisplayAlerts = $false
            $excel.AskToUpdateLinks = $false

            $book = $excel.Workbooks.Open($working, 0, $false)

            $deRowsResult = @(Paste-CsvToSheet $excel $book $de.FullName "出馬表" 44)
            if ($deRowsResult.Count -lt 1) {
                Fail "出馬表CSVの行数を取得できませんでした。"
            }
            $deRows = [int]$deRowsResult[-1]

            $null = @(Paste-CsvToSheet $excel $book $wood.FullName "ウッド調教表" 25)
            $null = @(Paste-CsvToSheet $excel $book $hill.FullName "坂路調教表" 19)

            $wsWood = $book.Worksheets.Item("ウッド調教表")
            if ($wsWood.Range("Z2").HasFormula) {
                $lastW = [int]$wsWood.UsedRange.Rows.Count
                if ($lastW -gt 2) { $null = $wsWood.Range("Z2:Z$lastW").FillDown() }
            }

            $wsHill = $book.Worksheets.Item("坂路調教表")
            if ($wsHill.Range("T2").HasFormula) {
                $lastH = [int]$wsHill.UsedRange.Rows.Count
                if ($lastH -gt 2) { $null = $wsHill.Range("T2:T$lastH").FillDown() }
            }

            $excel.CalculateFullRebuild()
            try { $excel.CalculateUntilAsyncQueriesDone() } catch {}
            $book.Save()

            Write-Host ""
            Write-Host "[2/6] メイン判定を training_current 用に書き出し" -ForegroundColor Yellow

            $main = $book.Worksheets.Item("メイン判定")
            $rowsOut = $deRows
            $colsOut = 89

            if ($rowsOut -lt 1) {
                Fail "メイン判定の出力行数が0です。出馬表貼付結果を確認してください。"
            }

            $tmpBook = $excel.Workbooks.Add()
            try {
                $tmpSheet = $tmpBook.Worksheets.Item(1)

                # PowerShell + Excel COM compatibility:
                # use A1-style range to avoid DISP_E_TYPEMISMATCH.
                $lastCell = "CK$rowsOut"
                $srcRange = $main.Range("A1:$lastCell")
                $dstRange = $tmpSheet.Range("A1:$lastCell")
                $dstRange.Value2 = $srcRange.Value2

                if (Test-Path $rawExport) {
                    Remove-Item $rawExport -Force
                }

                $xlCSVUTF8 = 62
                $tmpBook.SaveAs($rawExport, $xlCSVUTF8)
            }
            finally {
                $tmpBook.Close($false)
            }
        }
        finally {
            if ($null -ne $book) {
                try { $book.Close($true) } catch {}
            }
            if ($null -ne $excel) {
                try { $excel.Quit() } catch {}
                try {
                    [System.Runtime.Interopservices.Marshal]::ReleaseComObject($excel) | Out-Null
                } catch {}
            }
            [GC]::Collect()
            [GC]::WaitForPendingFinalizers()
        }

        Run-Python -PyArgs @(
            "scripts/normalize_training_current.py",
            "--raw", $rawExport,
            "--out", (RepoPath $Cfg.training_output)
        )

        Write-Host ""
        Write-Host "[3/6] A3履歴を更新" -ForegroundColor Yellow
        Run-Python -PyArgs @("scripts/update_a3_history.py")
    }

    if (-not $SkipHistory) {
        Write-Host ""
        Write-Host "[4/6] RaceDevelopment history_seed を差分更新" -ForegroundColor Yellow

        Run-Python -PyArgs @(
            "scripts/update_history_seed.py",
            "--horse", $horse.FullName,
            "--race", $race.FullName,
            "--master", (RepoPath $Cfg.history_master),
            "--backup-dir", (RepoPath $Cfg.backup_dir)
        )
    }

    Write-Host ""
    Write-Host "[5/6] 更新ファイル確認" -ForegroundColor Yellow
    Run-Python -PyArgs @("scripts/validate_nexus_update.py")

    if (-not $NoGit) {
        Write-Host ""
        Write-Host "[6/6] Git commit & push" -ForegroundColor Yellow

        $paths = @(
            $Cfg.training_output,
            $Cfg.a3_history,
            $Cfg.history_master
        )

        foreach ($p in $paths) {
            if (Test-Path (RepoPath $p)) {
                Run -Exe "git" -CmdArgs @("add","--",$p)
            }
        }

        & git diff --cached --quiet
        $diffRc = $LASTEXITCODE

        if ($diffRc -eq 0) {
            Write-Host "Gitに送る変更はありません。" -ForegroundColor DarkYellow
            Log "No staged changes."
        }
        else {
            $stamp = Get-Date -Format "yyyy-MM-dd HH:mm"
            Run -Exe "git" -CmdArgs @("commit","-m","Update Nexus race/training data $stamp")
            Run -Exe "git" -CmdArgs @("push",$Cfg.git_remote,$Cfg.git_branch)
            Write-Host "GitHub push 完了。Streamlit Cloudへ自動反映されます。" -ForegroundColor Green
            Log "Git push complete."
        }
    }

    Write-Host ""
    Write-Host "=== UPDATE COMPLETE ===" -ForegroundColor Green
    Log "UPDATE COMPLETE"
    exit 0
}
catch {
    $msg = $_.Exception.Message
    Write-Host ""
    Write-Host "==============================================" -ForegroundColor Red
    Write-Host "UPDATE FAILED" -ForegroundColor Red
    Write-Host "==============================================" -ForegroundColor Red
    Write-Host $msg -ForegroundColor Red
    Write-Host ""
    Write-Host "ログ: $LogPath" -ForegroundColor Yellow

    try {
        Log "FAILED: $msg"
        Add-Content -Path $LogPath -Value ($_ | Out-String) -Encoding UTF8
    } catch {}

    exit 1
}
