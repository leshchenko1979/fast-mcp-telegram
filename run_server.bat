@echo on
chcp 65001
echo [1/4] Установка PYTHONPATH
set PYTHONPATH=%PYTHONPATH%;C:\Users\leshc\python_projects\tg_mcp
echo [2/4] Проверка наличия Python
where python
echo [3/4] Запуск MCP сервера
mcp run src\server.py >> C:\Users\leshc\python_projects\tg_mcp\logs\mcp_server.log 2>&1
echo [4/4] Сервер завершил работу. Нажмите любую клавишу для выхода.
pause
