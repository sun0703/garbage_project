# Branch Protection Setup Script - Final Stable Version
# Based on verified working version with improvements

$Owner = "sun0703"
$Repo = "garbage_project"
$Branch = "main"

Write-Host "========================================"
Write-Host "  GitHub Branch Protection Setup v2.0"
Write-Host "========================================"
Write-Host ""

Write-Host "[*] Checking authentication..."
$authCheck = gh auth status 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[!] Not logged in. Starting login..." -ForegroundColor Yellow
    gh auth login --web --git-protocol https
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Login failed" -ForegroundColor Red
        exit 1
    }
}

$userInfo = gh api user --jq '.login' 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Logged in as: $userInfo" -ForegroundColor Green
} else {
    Write-Host "[ERROR] Verification failed" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Target: $Owner/$Repo | Branch: $Branch"
Write-Host ""

$branchInfo = gh api "/repos/$Owner/$Repo/branches/$Branch" 2>$null
if (-not $branchInfo) {
    Write-Host "[ERROR] Branch '$Branch' does not exist" -ForegroundColor Red
    exit 1
}

Write-Host "[*] Building JSON payload..."

$nl = [Environment]::NewLine
$sb = New-Object System.Text.StringBuilder

[void]$sb.Append("{$nl")
[void]$sb.Append("  ""required_status_checks"": {$nl")
[void]$sb.Append("    ""strict"": true,$nl")
[void]$sb.Append("    ""contexts"": [$nl")
[void]$sb.Append("      ""CI/CD Pipeline / Code Style Check"",$nl")
[void]$sb.Append("      ""CI/CD Pipeline / Unit Tests"",$nl")
[void]$sb.Append("      ""CI/CD Pipeline / Build Verification""$nl")
[void]$sb.Append("    ]$nl")
[void]$sb.Append("  },$nl")
[void]$sb.Append("  ""enforce_admins"": true,$nl")
[void]$sb.Append("  ""required_pull_request_reviews"": {$nl")
[void]$sb.Append("    ""dismiss_stale_reviews"": true,$nl")
[void]$sb.Append("    ""require_code_owner_reviews"": false,$nl")
[void]$sb.Append("    ""required_approving_review_count"": 1$nl")
[void]$sb.Append("  },$nl")
[void]$sb.Append("  ""restrictions"": null,$nl")
[void]$sb.Append("  ""required_linear_history"": true,$nl")
[void]$sb.Append("  ""allow_force_pushes"": false,$nl")
[void]$sb.Append("  ""allow_deletions"": false$nl")
[void]$sb.Append("}")

$jsonPayload = $sb.ToString()

Write-Host "[*] Configuring branch protection..."

$tempFile = "$env:TEMP\branch-protection-$((Get-Random)).json"
[System.IO.File]::WriteAllText($tempFile, $jsonPayload, [System.Text.UTF8Encoding]::new($false))

$result = gh api --method PUT "/repos/$Owner/$Repo/branches/$Branch/protection" --input $tempFile 2>&1

if (Test-Path $tempFile) {
    Remove-Item $tempFile -Force -ErrorAction SilentlyContinue
}

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "[SUCCESS] Branch protection configured!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Enabled protections:"
    Write-Host "  [v] PR review required (min 1 approval)"
    Write-Host "  [v] Status checks required (test/lint/build)"
    Write-Host "  [v] Strict mode enabled"
    Write-Host "  [v] Linear history enforced (Squash merge)"
    Write-Host "  [x] Force push disabled"
    Write-Host "  [x] Branch deletion disabled"
    Write-Host "  [x] Admins must follow rules too"
    Write-Host ""
    Write-Host "View settings: " -NoNewline
    Write-Host "https://github.com/$Owner/$Repo/settings/branches" -ForegroundColor Blue
    Write-Host ""
    exit 0
} else {
    Write-Host ""
    Write-Host "[ERROR] Failed to configure branch protection" -ForegroundColor Red
    Write-Host "Details: $result" -ForegroundColor Red
    Write-Host ""
    Write-Host "Manual setup:" -ForegroundColor Yellow
    Write-Host "  https://github.com/$Owner/$Repo/settings/branches" -ForegroundColor Yellow
    exit 1
}
