@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto :python
set "GM_PYTHON=py -3"
goto :found
:python
set "GM_PYTHON=python"
where python >nul 2>nul
if errorlevel 1 goto :missing
:found
echo Building Krampuslauf 1.8.0-beta.4 with %GM_PYTHON%...
%GM_PYTHON% -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :failed
%GM_PYTHON% -m PyInstaller --noconfirm --clean --onedir --windowed --name Krampuslauf --icon "assets\Krampuslauf.ico" --collect-all pythonnet --collect-all clr_loader Krampuslauf.py
if errorlevel 1 goto :failed
echo.
if exist "assets" xcopy /E /I /Y "assets" "dist\Krampuslauf\assets" >nul
if errorlevel 1 goto :failed
if exist "docs" xcopy /E /I /Y "docs" "dist\Krampuslauf\docs" >nul
if errorlevel 1 goto :failed
for %%F in (krampuslauf_bridge.py README.md CONFIGURATION.md CHANGELOG.md VERSION.txt LICENSE) do (
    copy /Y "%%F" "dist\Krampuslauf\%%F" >nul
    if errorlevel 1 goto :failed
)
echo EXE: dist\Krampuslauf\Krampuslauf.exe
echo Keep the entire dist\Krampuslauf directory together.
pause
exit /b 0
:missing
echo Python 3.12 or newer was not found. Install it and try again.
goto :failed
:failed
echo.
echo Build failed. Review the errors above.
pause
exit /b 1
