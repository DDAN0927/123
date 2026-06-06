@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo   Installing Global npm Packages (D: Drive)
echo ========================================

set "NODE_DIR=C:\Program Files\nodejs"
set "PREFIX=D:\dev-tools\node-global"

echo.
echo [1/2] Configuring npm...
call "%NODE_DIR%\npm.cmd" config set prefix "%PREFIX%"
call "%NODE_DIR%\npm.cmd" config set cache "D:\dev-tools\node-cache"
call "%NODE_DIR%\npm.cmd" config set registry https://registry.npmmirror.com
echo   OK: npm configured

echo.
echo [2/2] Installing global packages...
set PKGS=typescript ts-node @vue/cli create-vite tailwindcss prettier eslint nodemon pm2 serve

for %%P in (%PKGS%) do (
    echo   Installing %%P ...
    call "%NODE_DIR%\npm.cmd" install -g %%P --prefix "%PREFIX%" >nul 2>&1
    if !errorlevel! equ 0 (
        echo     OK
    ) else (
        echo     FAIL
    )
)

echo.
echo [3/3] Listing installed packages:
if exist "%PREFIX%\node_modules" (
    dir /b "%PREFIX%\node_modules" 2>nul
) else (
    echo   No packages found yet - PATH may need refresh
)

echo.
echo ========================================
echo   DONE!
echo ========================================
echo.
echo Close ALL terminals and reopen, then run:
echo   node --version
echo   npm --version
echo   pnpm --version
