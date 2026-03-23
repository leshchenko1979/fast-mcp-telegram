#!/bin/bash

echo "=== Application Health ==="
source .env
curl -s "https://${DOMAIN:-your-domain.com}/health" | jq .

echo ""
echo "=== VDS Container Stats ==="
ssh "${VDS_USER}@${VDS_HOST}" "docker stats fast-mcp-telegram --no-stream --format 'table {{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}'"
echo ""
