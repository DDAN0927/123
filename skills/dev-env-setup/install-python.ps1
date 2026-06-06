# ============================================================
# Python 开发环境安装脚本 (D盘版)
# 前提: 已运行 init-dev-env.ps1
# 用法: .\install-python.ps1
# ============================================================

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Python 开发环境安装 (D盘版)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$PYTHON_ROOT = "D:\dev-tools\Python"
$PYTHON_VERSION = "3.12"

Write-Host "`n[1/4] 下载 Python $PYTHON_VERSION ..." -ForegroundColor Yellow
$installerUrl = "https://www.python.org/ftp/python/3.12.9/python-3.12.9-amd64.exe"
$installerPath = "$env:TEMP\python-installer.exe"
if (-not (Test-Path "$PYTHON_ROOT\python.exe")) {
    Write-Host "  Downloading from python.org..." -ForegroundColor White
    Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath -UseBasicParsing
    Write-Host "  Installing to $PYTHON_ROOT ..." -ForegroundColor White
    Start-Process -FilePath $installerPath -ArgumentList "/quiet InstallAllUsers=0 TargetDir=$PYTHON_ROOT PrependPath=1 Include_pip=1" -Wait
    Remove-Item $installerPath -Force -ErrorAction SilentlyContinue
    Write-Host "  OK: Python installed" -ForegroundColor Green
} else {
    Write-Host "  Already installed at $PYTHON_ROOT" -ForegroundColor DarkGray
}

Write-Host "`n[2/4] 配置 pip 镜像源..." -ForegroundColor Yellow
$pipConfigDir = "$env:APPDATA\pip"
New-Item -ItemType Directory -Force -Path $pipConfigDir | Out-Null
$pipIni = @"
[global]
index-url = https://pypi.tuna.tsinghua.edu.cn/simple
trusted-host = pypi.tuna.tsinghua.edu.cn
timeout = 60
"@
Set-Content -Path "$pipConfigDir\pip.ini" -Value $pipIni -Encoding UTF8
Write-Host "  OK: pip using tsinghua mirror" -ForegroundColor Green

Write-Host "`n[3/4] 安装常用 Python 包..." -ForegroundColor Yellow
& "$PYTHON_ROOT\python.exe" -m pip install --upgrade pip -q 2>$null
$pyPkgs = @(
    "requests",           # HTTP请求
    "fastapi",            # Web框架
    "uvicorn[standard]",  # ASGI服务器
    "sqlalchemy",         # ORM
    "pymysql",            # MySQL驱动
    "python-dotenv",      # 环境变量
    "pillow",             # 图片处理
    "openpyxl",           # Excel处理
    "black",              # 代码格式化
    "ruff",               # linter
    "pytest",             # 测试框架
    "httpx",              # 异步HTTP
    "pydantic",           # 数据校验
    "jieba",              # 中文分词
    "cryptography"        # 加密
)
foreach ($pkg in $pyPkgs) {
    Write-Host -NoNewline "  $pkg ... "
    & "$PYTHON_ROOT\python.exe" -m pip install $pkg -q 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { Write-Host "OK" -ForegroundColor Green } else { Write-Host "SKIP" -ForegroundColor DarkGray }
}

Write-Host "`n[4/4] 添加到环境变量..." -ForegroundColor Yellow
$currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($currentPath -notlike "*$PYTHON_ROOT*") {
    [Environment]::SetEnvironmentVariable("Path", "$currentPath;$PYTHON_ROOT;$PYTHON_ROOT\Scripts", "User")
    Write-Host "  Added: $PYTHON_ROOT" -ForegroundColor Green
} else { Write-Host "  Already in PATH" -ForegroundColor DarkGray }

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Python 环境配置完成!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
