# ============================================================
# 开发环境一键初始化脚本 (D盘版)
# 用法: 右键 → 以管理员身份运行 PowerShell
#       Set-ExecutionPolicy Bypass -Scope Process -Force
#       .\init-dev-env.ps1
# ============================================================

param([switch]$Force)

$Host.UI.RawUI.WindowTitle = "Dev Environment Setup"
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Dev Environment Init (D: Drive)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$ErrorActionPreference = "SilentlyContinue"

$DEV_ROOT = "D:\dev-tools"
$NODE_GLOBAL = "$DEV_ROOT\node-global"
$NODE_CACHE = "$DEV_ROOT\node-cache"
$PNPM_HOME = "$DEV_ROOT\pnpm-home"
$PNPM_STORE = "$DEV_ROOT\pnpm-store"
$GIT_PATH = "D:\tools\Git\cmd"
$NODE_DIR = "C:\Program Files\nodejs"
$NPM_EXE = "$NODE_DIR\npm.exe"
$NODE_EXE = "$NODE_DIR\node.exe"
$GIT_EXE = "$GIT_PATH\git.exe"

function Run-Npm($args) { & $NPM_EXE $args }
function Run-Node($args) { & $NODE_EXE $args }
function Run-Git($args) { & $GIT_EXE $args }

# [1] Create directories
Write-Host "`n[1/7] Creating directories..." -ForegroundColor Yellow
@($NODE_GLOBAL, $NODE_CACHE, $PNPM_HOME, $PNPM_STORE) | ForEach-Object {
    New-Item -ItemType Directory -Force -Path $_ | Out-Null
}
Write-Host "  OK: $DEV_ROOT" -ForegroundColor Green

# [2] Configure npm
Write-Host "`n[2/7] Configuring npm..." -ForegroundColor Yellow
Run-Npm @("config", "set", "prefix", $NODE_GLOBAL) | Out-Null
Run-Npm @("config", "set", "cache", $NODE_CACHE) | Out-Null
Run-Npm @("config", "set", "registry", "https://registry.npmmirror.com") | Out-Null
Write-Host "  prefix:   $NODE_GLOBAL" -ForegroundColor Green
Write-Host "  cache:    $NODE_CACHE" -ForegroundColor Green
Write-Host "  registry: npmmirror.com" -ForegroundColor Green

# [3] Install pnpm
Write-Host "`n[3/7] Installing pnpm..." -ForegroundColor Yellow
Run-Npm @("install", "-g", "pnpm") | Out-Null
Write-Host "  OK: pnpm installed" -ForegroundColor Green

# [4] Configure pnpm
Write-Host "`n[4/7] Configuring pnpm..." -ForegroundColor Yellow
$pnpmExe = Get-ChildItem "$NODE_GLOBAL\pnpm.cmd" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($pnpmExe) {
    & $pnpmExe.FullName @("config", "set", "store-dir", $PNPM_STORE) | Out-Null
    & $pnpmExe.FullName @("config", "set", "global-bin-dir", $PNPM_HOME) | Out-Null
    & $pnpmExe.FullName @("config", "set", "registry", "https://registry.npmmirror.com") | Out-Null
    Write-Host "  store:     $PNPM_STORE" -ForegroundColor Green
} else {
    Write-Host "  WARN: pnpm not found at expected path" -ForegroundColor DarkGray
}

# [5] Configure Git
Write-Host "`n[5/7] Configuring Git..." -ForegroundColor Yellow
Run-Git @("config", "--global", "user.name", "Developer") | Out-Null
Run-Git @("config", "--global", "user.email", "dev@example.com") | Out-Null
Run-Git @("config", "--global", "init.defaultBranch", "main") | Out-Null
Run-Git @("config", "--global", "core.autocrlf", "input") | Out-Null
Run-Git @("config", "--global", "http.postBuffer", "524288000") | Out-Null
Write-Host "  OK: Git configured" -ForegroundColor Green

# [6] Set environment variables
Write-Host "`n[6/7] Setting environment variables (User level)..." -ForegroundColor Yellow
$newPaths = @($NODE_GLOBAL, $PNPM_HOME, $GIT_PATH, $NODE_DIR)
$currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
$added = @()
foreach ($p in $newPaths) {
    if ($currentPath -notlike "*$p*") {
        $added += $p
        if ($currentPath) {
            $newVal = "$currentPath;$p"
        } else {
            $newVal = $p
        }
        [Environment]::SetEnvironmentVariable("Path", $newVal, "User")
        $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
    }
}
[Environment]::SetEnvironmentVariable("NODE_PATH", "$NODE_GLOBAL\node_modules", "User")
if ($added.Count -gt 0) {
    Write-Host "  Added to PATH:" -ForegroundColor Green
    foreach ($a in $added) { Write-Host "    $a" }
} else {
    Write-Host "  All paths already exist" -ForegroundColor DarkGray
}

# [7] Install global packages
Write-Host "`n[7/7] Installing global packages..." -ForegroundColor Yellow
$globalPkgs = @(
    "typescript",
    "ts-node",
    "@vue/cli",
    "create-vite",
    "tailwindcss",
    "prettier",
    "eslint",
    "nodemon",
    "pm2",
    "serve"
)
foreach ($pkg in $globalPkgs) {
    Write-Host -NoNewline "  $pkg ... "
    Run-Npm @("install", "-g", $pkg) 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { Write-Host "OK" -ForegroundColor Green }
    else { Write-Host "SKIP" -ForegroundColor DarkGray }
}

# Done!
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  DONE! Environment initialized." -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "NEXT STEPS:" -ForegroundColor Yellow
Write-Host "  1. Close ALL terminal windows" -ForegroundColor White
Write-Host "  2. Reopen terminal" -ForegroundColor White
Write-Host "  3. Verify:" -ForegroundColor White
Write-Host "     node --version" -ForegroundColor Gray
Write-Host "     npm --version" -ForegroundColor Gray
Write-Host "     pnpm --version" -ForegroundColor Gray
Write-Host "     git --version" -ForegroundColor Gray
Write-Host ""
Write-Host "OPTIONAL:" -ForegroundColor Yellow
Write-Host "  Python:   .\install-python.ps1" -ForegroundColor Gray
Write-Host "  VSCode:   .\install-vscode-extensions.ps1" -ForegroundColor Gray
