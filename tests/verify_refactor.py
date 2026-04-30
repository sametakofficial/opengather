import sys
import os
import logging
from datetime import datetime

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from archiverr.state.manager import GlobalStateManager
from archiverr.state.models import RunState, JobState, StateEnum
from archiverr.infrastructure.database import DatabaseConnection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_refactor")

class ConsoleDebugger:
    def info(self, component, message, **kwargs):
        print(f"INFO [{component}] {message} {kwargs}")
    def debug(self, component, message, **kwargs):
        print(f"DEBUG [{component}] {message} {kwargs}")
    def warn(self, component, message, **kwargs):
        print(f"WARN [{component}] {message} {kwargs}")
    def error(self, component, message, **kwargs):
        print(f"ERROR [{component}] {message} {kwargs}")

def verify_flat_structure():
    logger.info("Verifying flat data structure...")
    
    # Setup
    try:
        persistence = DatabaseConnection.from_env().connect()
    except ImportError as e:
        logger.error(f"Failed to import MongoDB/pymongo: {e}")
        return False
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        return False
    
    debugger = ConsoleDebugger()
    state = GlobalStateManager(persistence=persistence, debugger=debugger)
    state.reset()
    
    # 1. Start Run
    config = {"plugins": {"test_plugin": {"enabled": True}}}
    run_id = state.start_run(config)
    logger.info(f"Run started: {run_id}")
    
    # 2. Create Job
    job_id = state.create_job("test_input", {"source": "manual"})
    logger.info(f"Job created: {job_id}")
    
    # 3. Update Plugin Data (Flat)
    plugin_data = {"processed": True, "score": 95}
    state.update_plugin(job_id, "test_plugin", plugin_data)
    
    # 4. Verify Job State
    job = state.get_job_by_id(job_id)
    if not job:
        logger.error("Job not found in state")
        return False
        
    # Check plugins dict directly
    if "test_plugin" not in job.plugins:
        logger.error("Plugin data not found in job.plugins")
        return False
        
    stored_data = job.plugins["test_plugin"]
    if stored_data != plugin_data:
        logger.error(f"Plugin data mismatch. Expected {plugin_data}, got {stored_data}")
        return False
        
    # Check if 'status' wrapper is absent (it should be absent in the data value)
    if "status" in stored_data and isinstance(stored_data["status"], dict) and "success" in stored_data["status"]:
         logger.warning("Found potential legacy 'status' wrapper in plugin data")
         
    # 5. Verify Persistence
    persisted_plugin = persistence.get_plugin(job_id, "test_plugin")
    if not persisted_plugin:
        logger.error("Plugin data not found in persistence")
        return False
        
    # DatabaseConnection stores what is passed to save_plugin.
    # Canonical writer chain (S36 PASS 2): services.update_plugin
    #   -> GlobalStateManager.update_plugin -> PluginDataManager._update_job_plugin
    #   -> persistence.save_plugin(plugin_doc)
    # plugin_doc has keys: job_id, plugin_name, data, run_id, job_index
    
    logger.info(f"Persisted plugin doc: {persisted_plugin}")
    
    if persisted_plugin["data"] != plugin_data:
         logger.error(f"Persisted data mismatch. Expected {plugin_data}, got {persisted_plugin['data']}")
         return False

    if "stage" in persisted_plugin:
        logger.error("Legacy 'stage' field found in persisted plugin")
        return False

    logger.info("Flat structure verification passed!")
    return True

def verify_orchestrator_interaction():
    logger.info("\nVerifying Orchestrator interaction...")
    
    # We won't run full orchestrator here as it requires complex setup,
    # but we'll check if we can complete a run without branch args
    
    try:
        persistence = DatabaseConnection.from_env().connect()
    except ImportError as e:
        logger.error(f"Failed to import MongoDB/pymongo: {e}")
        return False
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        return False
    
    state = GlobalStateManager(persistence=persistence)
    state.reset()
    
    state.start_run({})
    
    try:
        # This should NOT fail with "unexpected keyword argument 'branch_name'"
        state.complete_run() 
        logger.info("complete_run() succeeded without arguments")
    except TypeError as e:
        logger.error(f"complete_run() failed: {e}")
        return False
    except Exception as e:
        logger.error(f"complete_run() failed with unexpected error: {e}")
        return False
        
    return True

if __name__ == "__main__":
    success = True
    if not verify_flat_structure():
        success = False
    
    if not verify_orchestrator_interaction():
        success = False
        
    if success:
        logger.info("\nALL CHECKS PASSED")
        sys.exit(0)
    else:
        logger.error("\nSOME CHECKS FAILED")
        sys.exit(1)
