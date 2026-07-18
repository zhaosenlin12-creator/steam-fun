@echo off
cd /D "%~dp0\.."
set PYTHONPATH=%CD%\src
"C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe" -u -m steamfun_mirror.cli serve --port 8765 > runtime\s8765.out 2> runtime\s8765.err
