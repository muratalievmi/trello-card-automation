@echo off
REM Запуск CS2 Claude Console.
REM Перед первым запуском: py -m pip install -r requirements.txt
REM Ключ: set ANTHROPIC_API_KEY=sk-ant-...

if "%ANTHROPIC_API_KEY%"=="" (
    echo [!] ANTHROPIC_API_KEY не задан.
    echo     В этом окне выполните:  set ANTHROPIC_API_KEY=sk-ant-...
    pause
    exit /b 1
)

py "%~dp0overlay.py"
