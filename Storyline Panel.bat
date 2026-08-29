@echo off
rem Storyline Panel -- cift tiklayip acin.
rem pythonw.exe kullaniliyor: arkada konsol penceresi acilmaz.
start "" "%~dp0storyline-mcp\.venv\Scripts\pythonw.exe" "%~dp0storyline-mcp\panel\app.py"
