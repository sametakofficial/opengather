"""RFC 7396 JSON Merge Patch.

S40 — ``services.update_state(patch, mode='merge')`` applies this to the
run snapshot. ``null`` deletes a key. Nested objects recurse. Scalars
and arrays replace.
"""

from typing import Any


def merge_patch(target: Any, patch: Any) -> Any:
    """Apply an RFC 7396 Merge Patch.

    Args:
        target: Existing JSON-like value.
        patch: Patch document.

    Returns:
        New value. ``target`` is not mutated.
    """
    if not isinstance(patch, dict):
        return patch
    if not isinstance(target, dict):
        target = {}
    result = dict(target)
    for key, value in patch.items():
        if value is None:
            result.pop(key, None)
        elif isinstance(value, dict):
            result[key] = merge_patch(result.get(key), value)
        else:
            result[key] = value
    return result
