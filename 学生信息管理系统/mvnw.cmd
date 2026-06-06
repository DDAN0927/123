@REM Maven Wrapper startup batch script
@echo off
setlocal

set MAVEN_VERSION=3.9.16
set MAVEN_URL=https://dlcdn.apache.org/maven/maven-3/%MAVEN_VERSION%/binaries/apache-maven-%MAVEN_VERSION%-bin.zip
set MAVEN_HOME=%~dp0.mvn\maven\apache-maven-%MAVEN_VERSION%

if exist "%MAVEN_HOME%\bin\mvn.cmd" goto runMaven

echo Downloading Maven %MAVEN_VERSION%...
if not exist "%~dp0.mvn\maven" mkdir "%~dp0.mvn\maven"

powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%MAVEN_URL%' -OutFile '%~dp0.mvn\maven\maven.zip'"
powershell -Command "Expand-Archive -Path '%~dp0.mvn\maven\maven.zip' -DestinationPath '%~dp0.mvn\maven' -Force"
del "%~dp0.mvn\maven\maven.zip"

:runMaven
"%MAVEN_HOME%\bin\mvn.cmd" %*
