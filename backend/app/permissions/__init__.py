"""Authorization decisions for documents and folders.

`engine.can` answers a single check. `engine.accessible_documents_query` and
`engine.accessible_folders_query` are the list filters every document and folder
query goes through.
"""

from app.permissions.engine import (
    access_level,
    accessible_documents_query,
    accessible_folders_query,
    can,
    direct_folder_access_query,
    scope_ceiling,
)

__all__ = [
    "access_level",
    "accessible_documents_query",
    "accessible_folders_query",
    "can",
    "direct_folder_access_query",
    "scope_ceiling",
]
