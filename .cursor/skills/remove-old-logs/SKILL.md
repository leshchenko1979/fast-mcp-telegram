---
name: Remove Old Logs
description: Remove log files older than 1 day from logs directory
disable-model-invocation: true
---

Remove log files from /logs that are more than a day old. Use only shell commands:
find logs -name "*.log" -mtime +1 -delete
