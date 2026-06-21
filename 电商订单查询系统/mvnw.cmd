@REM Maven Wrapper startup script for Windows
@REM
@REM Required ENV vars:
@REM JAVA_HOME - location of a JDK home dir
@REM
@REM Optional ENV vars
@REM M2_HOME - location of maven2's installed home dir
@REM MAVEN_BATCH_ECHO - set to 'on' to enable the echoing of the batch commands
@REM MAVEN_BATCH_PAUSE - set to 'on' to wait for a key stroke before ending
@REM MAVEN_OPTS - parameters passed to the Java VM when running Maven

@echo off
setlocal

set WRAPPER_JAR="%MAVEN_PROJECTBASEDIR%\.mvn\wrapper\maven-wrapper.jar"
set WRAPPER_URL="https://repo.maven.apache.org/maven2/org/apache/maven/wrapper/maven-wrapper/3.2.0/maven-wrapper-3.2.0.jar"

if exist %WRAPPER_JAR% (
    if not exist "%MAVEN_PROJECTBASEDIR%\.mvn\wrapper\maven-wrapper.jar" (
        copy /Y "%WRAPPER_JAR%" "%MAVEN_PROJECTBASEDIR%\.mvn\wrapper\maven-wrapper.jar"
    )
) else (
    echo Downloading Maven Wrapper...
    powershell -Command "Invoke-WebRequest -Uri '%WRAPPER_URL%' -OutFile '%WRAPPER_JAR%'"
)

@REM Find JAVA_HOME
set JAVA_HOME=
for /f "tokens=1,2 delims= " %%a in ('"REG QUERY "HKLM\SOFTWARE\JavaSoft\Java Development Kit" /v CurrentVersion" 2^>nul') do set KEY=%%b
if defined KEY (
    for /f "tokens=1,2 delims= " %%a in ('"REG QUERY "HKLM\SOFTWARE\JavaSoft\Java Development Kit\%KEY%" /v JavaHome" 2^>nul') do set JAVA_HOME=%%b
)

@REM Find JDK
if not defined JAVA_HOME (
    for /f "tokens=1,2 delims= " %%a in ('"REG QUERY "HKLM\SOFTWARE\JavaSoft\JDK" /v CurrentVersion" 2^>nul') do set KEY=%%b
    if defined KEY (
        for /f "tokens=1,2 delims= " %%a in ('"REG QUERY "HKLM\SOFTWARE\JavaSoft\JDK\%KEY%" /v JavaHome" 2^>nul') do set JAVA_HOME=%%b
    )
)

@REM Find JAVA in PATH
if not defined JAVA_HOME (
    for /f "tokens=1,2 delims= " %%a in ('where java 2^>nul') do (
        if not defined JAVA_BIN set JAVA_BIN=%%a
    )
    if defined JAVA_BIN (
        for /f "tokens=* delims=" %%a in ('"%JAVA_BIN:~0,-9%\java.exe" -XshowSettings:properties -version 2^>nul ^| findstr "java.home"') do set JAVA_HOME=%%a
        set JAVA_HOME=%JAVA_HOME:~10%
    )
)

if not defined JAVA_HOME (
    echo ERROR: JAVA_HOME is not set and Java could not be found in PATH.
    echo Please install JDK 21 or higher and set JAVA_HOME environment variable.
    echo.
    echo You can download JDK from: https://adoptium.net/
    exit /b 1
)

set MAVEN_OPTS=%MAVEN_OPTS% -Xms256m -Xmx512m

"%JAVA_HOME%\bin\java.exe" ^
  -jar "%WRAPPER_JAR%" ^
  %*
