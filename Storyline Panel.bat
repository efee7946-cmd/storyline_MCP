@echo off
setlocal
rem Storyline Panel -- cift tiklayip acin.
rem pythonw.exe kullaniliyor: arkada konsol penceresi acilmaz.

set "PY=%~dp0storyline-mcp\.venv\Scripts\pythonw.exe"

rem KURULUM EKSIKSE SESSIZ KALMA. pythonw.exe surece stdout/stderr vermez,
rem dolayisiyla eksik bir sanal ortam ya da eksik pywebview "hicbir yere
rem dusmeyen bir hata + hic acilmayan bir pencere" olarak gorunur. Kullanici
rem cift tiklar ve HICBIR SEY olur. Olculdu 2026-08-29, temiz klonda.
if not exist "%PY%" (
  echo.
  echo   Sanal ortam bulunamadi:
  echo   %PY%
  echo.
  echo   Kurulum icin depo kokunde su iki komutu calistirin:
  echo.
  echo       cd storyline-mcp
  echo       python -m venv .venv
  echo       .venv\Scripts\python.exe -m pip install -e ".[panel]"
  echo.
  pause
  exit /b 1
)

start "" "%PY%" "%~dp0storyline-mcp\panel\app.py"
