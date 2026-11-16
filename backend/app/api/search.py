from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.enums import SourceType
from app.core.errors import ApiError
from app.core.principal import SCOPE_DOCS_READ, Principal, require_scope
from app.schemas.search import SearchResponse, SuggestResponse, to_search_response, to_suggest_response
from app.services.search import DEFAULT_PAGE_SIZE, PAGE_SIZE_CAP, SearchParams, SearchService

router = APIRouter()

READER = Depends(require_scope(SCOPE_DOCS_READ))


@router.get("/suggest", response_model=SuggestResponse)
def get_suggestions(
    principal: Principal = READER,
    session: Session = Depends(get_db),
    q: str = Query(default="", max_length=300),
) -> SuggestResponse:
    """Top eight document names the caller can view, for the command palette."""
    return to_suggest_response(SearchService(session).suggest(principal, q))


@router.get("", response_model=SearchResponse)
def get_search(
    principal: Principal = READER,
    session: Session = Depends(get_db),
    q: str = Query(default="", max_length=300),
    department: UUID | None = None,
    category: UUID | None = None,
    tags: list[str] | None = Query(default=None, description="Tag ids, repeated or comma-separated. A document must have every tag."),
    source_type: SourceType | None = Query(default=None, alias="type"),
    owner: UUID | None = None,
    modified_from: date | None = Query(default=None, alias="from"),
    modified_to: date | None = Query(default=None, alias="to"),
    include_archived: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=PAGE_SIZE_CAP),
) -> SearchResponse:
    """Search documents the caller can view. Results, snippets, and facets share one permission filter."""
    result = SearchService(session).search(
        principal,
        SearchParams(
            q=q,
            department_id=department,
            category_id=category,
            tag_ids=_tag_ids(tags),
            source_type=source_type,
            owner_id=owner,
            modified_from=modified_from,
            modified_to=modified_to,
            include_archived=include_archived,
            page=page,
            page_size=page_size,
        ),
    )
    return to_search_response(result)


def _tag_ids(values: list[str] | None) -> tuple[UUID, ...]:
    if not values:
        return ()
    parsed: list[UUID] = []
    for value in values:
        for part in value.split(","):
            text = part.strip()
            if not text:
                continue
            try:
                parsed.append(UUID(text))
            except ValueError as exc:
                raise ApiError(422, "INVALID_TAG", "Tag ids must be UUIDs.") from exc
    return tuple(parsed)
