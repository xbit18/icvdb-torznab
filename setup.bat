
@echo off
setlocal
cd /d "%~dp0"

echo === Checking prerequisites ===
where npm >nul 2>&1 || (echo npm not found & exit /b 1)
where py >nul 2>&1 || (echo Python launcher not found & exit /b 1)

echo === Installing root dependencies ===
call npm ci --include=dev || exit /b 1

echo === Installing frontend dependencies ===
pushd frontend
call npm ci --include=dev
if errorlevel 1 (popd & exit /b 1)
popd

echo === Installing docs dependencies ===
pushd docs
call npm ci --include=dev
if errorlevel 1 (popd & exit /b 1)
popd

echo === Setting up Python ===
py -3 -m venv .venv || exit /b 1
.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt || exit /b 1

echo === Configuring Git hooks ===
git config --local core.hooksPath .githooks || exit /b 1

echo === Setup completed successfully! ===
endlocal
