# 分支保护规则配置脚本
# 使用前请确保已运行: gh auth login --web

param(
    [string]$Owner = "sun0703",
    [string]$Repo = "garbage_project",
    [string]$Branch = "main"
)

# 检查 gh 是否已安装
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Host "❌ 错误: GitHub CLI (gh) 未安装" -ForegroundColor Red
    Write-Host "请运行: winget install --id GitHub.cli" -ForegroundColor Yellow
    exit 1
}

# 检查是否已登录
$authStatus = gh auth status 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠️  未检测到 GitHub 登录，正在启动登录..." -ForegroundColor Yellow
    gh auth login --web
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ 登录失败，请手动运行: gh auth login --web" -ForegroundColor Red
        exit 1
    }
}

Write-Host "`n🔒 开始设置分支保护规则..." -ForegroundColor Cyan
Write-Host "📦 仓库: $Owner/$Repo" -ForegroundColor White
Write-Host "🌿 分支: $Branch`n" -ForegroundColor White

try {
    # 设置分支保护规则
    $body = @{
        required_status_checks = @{
            strict = $true
            contexts = @("ci/test", "ci/lint", "ci/build")
        }
        enforce_admins = $true
        required_pull_request_reviews = @{
            dismiss_stale_reviews = $true
            require_code_owner_reviews = $false
            required_approving_review_count = 1
        }
        restrictions = $null  # 不限制谁能推送，只限制方式
        required_linear_history = $true
        allow_force_pushes = $false
        allow_deletions = $false
        block_creations = $false
    } | ConvertTo-Json -Depth 5

    $result = gh api --method PUT `
        "/repos/$Owner/$Repo/branches/$Branch/protection" `
        --input - <<< $body
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ 分支保护规则设置成功！" -ForegroundColor Green
        
        Write-Host "`n📋 已启用的保护规则:" -ForegroundColor Cyan
        Write-Host "  ✓ 需要 PR 审查（至少 1 人批准）" -ForegroundColor Green
        Write-Host "  ✓ 状态检查必须通过（test/lint/build）" -ForegroundColor Green
        Write-Host "  ✓ 禁止强制推送（Force Push）" -ForegroundColor Green
        Write-Host "  ✓ 禁止删除主分支" -ForegroundColor Green
        Write-Host "  ✓ 要求线性提交历史（Squash Merge）" -ForegroundColor Green
        Write-Host "  ✓ 管理员也受规则约束" -ForegroundColor Green
        Write-Host "  ✓ 过期的审查意见会自动忽略" -ForegroundColor Green
    }
} catch {
    Write-Host "❌ 设置失败: $_" -ForegroundColor Red
    Write-Host "`n💡 可能的原因:" -ForegroundColor Yellow
    Write-Host "  1. 没有仓库管理员权限" -ForegroundColor Yellow
    Write-Host "  2. 网络连接问题" -ForegroundColor Yellow
    Write-Host "  3. 分支名称不正确" -ForegroundColor Yellow
    exit 1
}
