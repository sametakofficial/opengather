"""
Plugins API Router - Session 11 Phase 8

Endpoints for plugin information and data access.
"""

from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query

from archiverr.api.deps import DatabaseDep
from .schemas import PluginInfo, PluginData, PluginListResponse, PluginDataListResponse

router = APIRouter()


@router.get("", response_model=PluginListResponse)
async def list_plugins(db: DatabaseDep):
    """
    List all available plugins with their manifest info.
    """
    try:
        # Get plugin info from registry (runtime) or database
        from archiverr.core.plugins.registry import PluginRegistry
        from archiverr.utils.config_loader import load_config_with_tracking
        
        # Try to get from registry
        try:
            config = load_config_with_tracking("config.yml")
            registry = PluginRegistry(config)
            registry.discover_and_load()
            
            manifests = registry.get_all_manifests()
            
            plugins = [
                PluginInfo(
                    name=name,
                    version=manifest.get("version", "1.0.0"),
                    stage=manifest.get("stage", manifest.get("category", "output")),
                    requires=manifest.get("requires", []),
                    provides=manifest.get("provides", []),
                    trigger_rule=manifest.get("trigger_rule", "all_success"),
                    enabled=name in registry.enabled_plugins,
                    description=manifest.get("description")
                )
                for name, manifest in manifests.items()
            ]
            
            return PluginListResponse(items=plugins, total=len(plugins))
            
        except Exception:
            # Fallback: return empty list
            return PluginListResponse(items=[], total=0)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/data", response_model=PluginDataListResponse)
async def list_plugin_data(
    db: DatabaseDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    run_id: Optional[str] = Query(default=None),
    plugin_name: Optional[str] = Query(default=None)
):
    """
    List plugin data entries with filtering.
    """
    try:
        query = {}
        if run_id:
            query["run_id"] = run_id
        if plugin_name:
            query["plugin_name"] = plugin_name
        
        skip = (page - 1) * page_size
        
        cursor = db["plugins"].find(query).sort("created_at", -1).skip(skip).limit(page_size)
        docs = await cursor.to_list(length=page_size)
        
        total = await db["plugins"].count_documents(query)
        
        items = [
            PluginData(
                id=str(doc.get("_id", "")),
                job_id=doc.get("job_id", ""),
                run_id=doc.get("run_id", ""),
                plugin_name=doc.get("plugin_name", ""),
                stage=doc.get("stage", ""),
                data=doc.get("data", {}),
                status=doc.get("status", {}),
                created_at=doc.get("created_at")
            )
            for doc in docs
        ]
        
        return PluginDataListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/run/{run_id}", response_model=List[PluginData])
async def get_plugins_by_run(run_id: str, db: DatabaseDep):
    """
    Get all plugin data for a specific run.
    """
    try:
        cursor = db["plugins"].find({"run_id": run_id})
        docs = await cursor.to_list(length=1000)
        
        # Fallback to legacy collection
        if not docs:
            cursor = db["plugin_results"].find({"execution_id": run_id})
            docs = await cursor.to_list(length=1000)
        
        return [
            PluginData(
                id=str(doc.get("_id", "")),
                job_id=doc.get("job_id", doc.get("match_id", "")),
                run_id=doc.get("run_id", doc.get("execution_id", "")),
                plugin_name=doc.get("plugin_name", ""),
                stage=doc.get("stage", ""),
                data=doc.get("data", {}),
                status=doc.get("status", {}),
                created_at=doc.get("created_at")
            )
            for doc in docs
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{plugin_name}", response_model=PluginInfo)
async def get_plugin_info(plugin_name: str, db: DatabaseDep):
    """
    Get information about a specific plugin.
    """
    try:
        from archiverr.core.plugins.registry import PluginRegistry
        from archiverr.utils.config_loader import load_config_with_tracking
        
        config = load_config_with_tracking("config.yml")
        registry = PluginRegistry(config)
        registry.discover_and_load()
        
        manifest = registry.get_manifest(plugin_name)
        
        if not manifest:
            raise HTTPException(status_code=404, detail=f"Plugin not found: {plugin_name}")
        
        return PluginInfo(
            name=plugin_name,
            version=manifest.get("version", "1.0.0"),
            stage=manifest.get("stage", manifest.get("category", "output")),
            requires=manifest.get("requires", []),
            provides=manifest.get("provides", []),
            trigger_rule=manifest.get("trigger_rule", "all_success"),
            enabled=plugin_name in registry.enabled_plugins,
            description=manifest.get("description")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
