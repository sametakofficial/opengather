#!/bin/bash
cd /home/samet/Workspace/archiverr
source .venv/bin/activate
echo "Running archiverr..."
archiverr 2>&1 | tee /tmp/archiverr_test.log
echo "Exit code: $?"
echo "Output saved to /tmp/archiverr_test.log"
