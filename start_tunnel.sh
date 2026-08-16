#!/bin/bash
# XEROS public tunnel via localtunnel
export PATH=/opt/data/node-tools/node_modules/.bin:$PATH
nohup lt --port 8645 > /opt/data/xeros-app-server/tunnel.log 2>&1 &
echo $! > /opt/data/xeros-app-server/tunnel.pid
