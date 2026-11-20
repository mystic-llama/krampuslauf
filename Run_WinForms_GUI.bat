@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto :python
py -3 Krampuslauf.py
if not errorlevel 1 exit /b 0
:python
where python >nul 2>nul
if errorlevel 1 goto :missing
python Krampuslauf.py
if not errorlevel 1 exit /b 0
goto :failed
:missing
echo Python 3.12 or newer was not found. Install it, or edit this file to call your python.exe.
goto :failed
:failed
echo The GUI could not start. Check Python 3.12 or newer, requirements.txt and .NET Framework.
pause
exit /b 1
