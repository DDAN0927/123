@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo   补装缺失的 npm 全局包 (D盘)
echo ========================================

set "NPM=C:\Program Files\nodejs\npm.cmd"
set "PREFIX=D:\dev-tools\node-global"

echo.
echo Installing missing global packages...

set PKGS=@vue/cli create-next-app @nestjs/cli prisma commitizen @biomejs/biome

for %%P in (%PKGS%) do (
    echo   Installing %%P ...
    call "%NPM%" install -g %%P --prefix "%PREFIX%" >nul 2>&1
    if !errorlevel! equ 0 (
        echo     OK
    ) else (
        echo     FAIL
    )
)

echo.
echo Verifying installed packages:
for %%P in (%PKGS%) do (
    if exist "%PREFIX%\node_modules\%%P\package.json" (
        echo   OK: %%P
    ) else (
        echo   MISSING: %%P
    )
)

echo.
echo ========================================
echo   DONE!
echo ========================================
