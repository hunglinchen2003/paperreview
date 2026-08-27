@echo off
chcp 65001 > nul
echo ========================================================
echo  🧬 Galectin 文獻自動追蹤與 Ollama 綜述系統 WebUI
echo ========================================================
echo.

:: Check python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [錯誤] 找不到 Python，請確認已安裝 Python 3.9+ 並加入 PATH。
    pause
    exit /b 1
)

echo [1/2] 檢查並安裝必要依賴模組...
pip install -r requirements.txt

echo.
echo [2/2] 正在啟動 WebUI 伺服器 (http://127.0.0.1:8000)...
echo.
echo ========================================================
echo  請在瀏覽器打開: http://127.0.0.1:8000
echo  定時排程預設每天早上 02:00 AM 自動執行
echo  按 Ctrl+C 可關閉伺服器
echo ========================================================
echo.

python app.py

pause
