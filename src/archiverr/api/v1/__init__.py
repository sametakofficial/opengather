"""
API Version 1

Includes all v1 routers:
- run    (subprocess CLI proxy, blackbox trigger)
- runs   (canonical RESTful CRUD over runs)
- jobs   (read jobs by run / by id)
- plugins (cross-job plugin output query)
- system (health, version, diagnostics)
"""

from .router import router

__all__ = ["router"]
