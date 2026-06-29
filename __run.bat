@echo off
cd C:\Users\DT0038\Desktop\snowfllake

REM Kích hoạt môi trường ảo trong thư mục hiện tại
call venv\Scripts\activate.bat

REM Chạy script python
python main.py

REM (Tuỳ chọn) deactivate môi trường ảo
deactivate