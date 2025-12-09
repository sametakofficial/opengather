#!/bin/bash
# Quick Archiverr Test
set -x  # Show commands

echo "======================================"
echo "QUICK ARCHIVERR TEST"
echo "======================================"

cd /home/samet/Workspace/archiverr

echo ""
echo "1. Python version:"
python --version

echo ""
echo "2. Test import:"
python -c "import sys; sys.path.insert(0, 'src'); from archiverr.utils.debug import init_debugger; print('✅ Import OK')"

echo ""
echo "3. Test config:"
python -c "import sys; sys.path.insert(0, 'src'); from archiverr.utils.config_loader import load_config_with_tracking; c = load_config_with_tracking('config.yml'); print(f'✅ Config loaded: {len(c)} keys')"

echo ""
echo "4. Run archiverr:"
python -m archiverr

echo ""
echo "======================================"
echo "TEST COMPLETE"
echo "======================================"
