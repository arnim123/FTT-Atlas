from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.enums import DocumentStatus, SourceType
from app.schemas.documents import TagBrief, document_web_url

MatchField = Literal["name", "tag", "category", "description", "content"]


class FacetBucket(BaseModel):
    id: str
    name: str
    count: int


class SearchFacets(BaseModel):
    department: list[FacetBucket]
    category: list[FacetBucket]
    type: list[FacetBucket]
    tags: list[FacetBucket]


class SearchHitRead(BaseModel):
    id: UUID
    name: str
    description: str | None
    snippet: str
    matched_in: list[MatchField]
    score: float
    folder_id: UUID
    folder_path: str
    department_id: UUID
    department_name: str
    category_id: UUID
    category_name: str
    source_type: SourceType
    owner_id: UUID
    tags: list[TagBrief]
    status: DocumentStatus
    web_url: str
    google_url: str | None
    last_modified_at: datetime | None
    created_at: datetime


class SearchResponse(BaseModel):
    items: list[SearchHitRead]
    total: int
    page: int
    page_size: int = Field(le=50)
    facets: SearchFacets


class SuggestHit(BaseModel):
    id: UUID
    name: str


class SuggestResponse(BaseModel):
    items: list[SuggestHit] = Field(max_length=8)


def to_search_response(result) -> SearchResponse:
    return SearchResponse(
        items=[_hit(item) for item in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        facets=SearchFacets(
            department=[_bucket(bucket) for bucket in result.facets.department],
            category=[_bucket(bucket) for bucket in result.facets.category],
            type=[_bucket(bucket) for bucket in result.facets.type],
            tags=[_bucket(bucket) for bucket in result.facets.tags],
        ),
    )


def to_suggest_response(items) -> SuggestResponse:
    return SuggestResponse(items=[SuggestHit(id=item.id, name=item.name) for item in items])


def _hit(item) -> SearchHitRead:
    document = item.document
    return SearchHitRead(
        id=document.id,
        name=document.name,
        description=document.description,
        snippet=item.snippet,
        matched_in=item.matched_in,
        score=item.score,
        folder_id=document.folder_id,
        folder_path=item.folder_path,
        department_id=document.department_id,
        department_name=item.department_name,
        category_id=document.category_id,
        category_name=item.category_name,
        source_type=document.source_type,
        owner_id=document.owner_id,
        tags=[TagBrief(id=tag.id, name=tag.name) for tag in item.tags],
        status=document.status,
        web_url=document_web_url(document.id),
        google_url=document.google_web_url,
        last_modified_at=document.last_modified_at,
        created_at=document.created_at,
    )


def _bucket(bucket) -> FacetBucket:
    return FacetBucket(id=str(bucket.id), name=bucket.name, count=bucket.count)
