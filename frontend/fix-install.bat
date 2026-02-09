@echo off
REM 修復前端依賴安裝腳本

echo 🔧 清理舊的依賴...
if exist node_modules rmdir /s /q node_modules
if exist package-lock.json del package-lock.json

echo.
echo 📦 重新安裝依賴...
call npm install

echo.
echo ✅ 安裝完成！
echo.
echo 現在可以執行: npm start
pause
