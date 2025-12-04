#!/bin/bash

echo "=== Application Health ==="
source .env
curl -s "https://${DOMAIN:-your-domain.com}/health" | jq .

echo ""
echo "=== VDS Container Stats ==="
ssh "${VDS_USER:-root}@${VDS_HOST:-94.250.254.232}" "docker stats fast-mcp-telegram --no-stream --format 'table {{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}'"
echo ""
