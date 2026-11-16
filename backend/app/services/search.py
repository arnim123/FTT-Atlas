"""Permission-filtered search.

`SearchService.search` is the only search implementation. The web UI, the REST
API, and later MCP tools all call it. Phase 2 can replace the full-text and
trigram predicate inside `_criteria` with a hybrid or vector ranker without
changing the signature.

Every candidate row is produced by `accessible_documents_query`. Snippets,
facets, and suggestions are computed from that set. Nothing is fetched and
then dropped.
"""

from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, time
from uuid import UUID

from sqlalchemy import Text, case, cast, exists, func, literal, literal_column, or_, select
from sqlalchemy.dialects.postgresql import ARRAY, REGCONFIG, array
from sqlalchemy.orm import Session

from app.core.enums import DocumentStatus, SourceType
from app.core.errors import ApiError
from app.core.principal import Principal
from app.models.department import Department
from app.models.document import Document
from app.models.search import SearchLog
from app.models.taxonomy import Category, DocumentTag, Tag
from app.permissions.engine import accessible_documents_query
from app.services.activity import channel_for
from app.services.folders import folder_display_paths

PAGE_SIZE_CAP = 50
DEFAULT_PAGE_SIZE = 20
SUGGEST_LIMIT = 8
MAX_QUERY_LENGTH = 300
HEADLINE_OPTIONS = 'MaxFragments=2, MaxWords=28, MinWords=6, ShortWord=3, StartSel="", StopSel=""'


@dataclass(frozen=True)
class SearchParams:
    q: str = ""
    department_id: UUID | None = None
    category_id: UUID | None = None
    tag_ids: tuple[UUID, ...] = ()
    source_type: SourceType | None = None
    owner_id: UUID | None = None
    modified_from: date | None = None
    modified_to: date | None = None
    include_archived: bool = False
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE
    folder_id: UUID | None = None


@dataclass(frozen=True)
class FacetBucket:
    id: str
    name: str
    count: int


@dataclass
class SearchFacets:
    department: list[FacetBucket]
    category: list[FacetBucket]
    type: list[FacetBucket]
    tags: list[FacetBucket]


@dataclass
class SearchHit:
    document: Document
    snippet: str
    matched_in: list[str]
    score: float
    folder_path: str
    department_name: str
    category_name: str
    tags: list[Tag]


@dataclass
class SearchPageResult:
    items: list[SearchHit]
    total: int
    page: int
    page_size: int
    facets: SearchFacets


@dataclass(frozen=True)
class Suggestion:
    id: UUID
    name: str


class SearchService:
    def __init__(self, session: Session):
        self.session = session

    def search(self, principal: Principal, params: SearchParams) -> SearchPageResult:
        """Rank documents the principal can view. Writes one search_logs row."""
        params = _bounded(params)
        criteria = self._criteria(principal, params)
        total = self.session.scalar(select(func.count()).select_from(Document).where(*criteria)) or 0
        facets = self._facets(criteria)
        items = self._page(params, criteria) if total else []
        self._log(principal, params.q, total)
        return SearchPageResult(
            items=items,
            total=total,
            page=params.page,
            page_size=params.page_size,
            facets=facets,
        )

    def suggest(self, principal: Principal, query: str) -> list[Suggestion]:
        """Top document names for the command palette. Archived rows are omitted."""
        cleaned = query.strip()
        if not cleaned:
            return []
        if len(cleaned) > MAX_QUERY_LENGTH:
            raise ApiError(422, "QUERY_TOO_LONG", "Enter a search of 300 characters or fewer.")
        visible = [
            accessible_documents_query(principal.user, principal.scopes),
            Document.status == DocumentStatus.active,
        ]
        if len(cleaned) >= 3:
            match = Document.name.op("%>")(cleaned)
            order = (func.word_similarity(cleaned, Document.name).desc(), Document.name.asc(), Document.id.asc())
        else:
            match = Document.name.ilike(_like_prefix(cleaned), escape="\\")
            order = (Document.name.asc(), Document.id.asc())
        rows = self.session.execute(
            select(Document.id, Document.name).where(*visible, match).order_by(*order).limit(SUGGEST_LIMIT)
        ).all()
        return [Suggestion(id=row.id, name=row.name) for row in rows]

    def match_statement(self, principal: Principal, params: SearchParams):
        """The permission-filtered id select `search` filters with.

        Tests EXPLAIN this statement. The text predicate is the part Phase 2
        replaces; the accessible-document clause stays.
        """
        params = _bounded(params)
        return select(Document.id).where(*self._criteria(principal, params))

    def _criteria(self, principal: Principal, params: SearchParams) -> list:
        criteria = [accessible_documents_query(principal.user, principal.scopes)]
        if not params.include_archived:
            criteria.append(Document.status == DocumentStatus.active)
        if params.department_id is not None:
            criteria.append(Document.department_id == params.department_id)
        if params.category_id is not None:
            criteria.append(Document.category_id == params.category_id)
        if params.owner_id is not None:
            criteria.append(Document.owner_id == params.owner_id)
        if params.folder_id is not None:
            criteria.append(Document.folder_id == params.folder_id)
        if params.source_type is not None:
            criteria.append(Document.source_type == params.source_type)
        modified = func.coalesce(Document.last_modified_at, Document.created_at)
        if params.modified_from is not None:
            criteria.append(modified >= datetime.combine(params.modified_from, time.min, tzinfo=UTC))
        if params.modified_to is not None:
            criteria.append(modified <= datetime.combine(params.modified_to, time.max, tzinfo=UTC))
        for tag_id in params.tag_ids:
            criteria.append(
                exists(
                    select(DocumentTag.id)
                    .where(
                        DocumentTag.document_id == Document.id,
                        DocumentTag.tag_id == tag_id,
                    )
                    .correlate(Document)
                )
            )
        if params.q:
            criteria.append(_text_predicate(params.q))
        return criteria

    def _page(self, params: SearchParams, criteria: list) -> list[SearchHit]:
        score = _rank(params.q).label("score")
        ranked = (
            select(Document.id.label("id"), score)
            .where(*criteria)
            .order_by(score.desc(), Document.last_modified_at.desc().nulls_last(), Document.id.asc())
            .offset((params.page - 1) * params.page_size)
            .limit(params.page_size)
            .subquery()
        )
        rows = self.session.execute(
            select(
                Document,
                Department.name,
                Category.name,
                _snippet(params.q).label("snippet"),
                _matched_in(params.q).label("matched_in"),
                ranked.c.score,
            )
            .join(ranked, ranked.c.id == Document.id)
            .join(Department, Department.id == Document.department_id)
            .join(Category, Category.id == Document.category_id)
            .order_by(ranked.c.score.desc(), Document.last_modified_at.desc().nulls_last(), Document.id.asc())
        ).all()
        document_ids = [row[0].id for row in rows]
        tags = _tags_for(self.session, document_ids)
        paths = folder_display_paths(self.session, {row[0].folder_id for row in rows})
        hits: list[SearchHit] = []
        for document, department_name, category_name, snippet, matched_in, score_value in rows:
            hits.append(
                SearchHit(
                    document=document,
                    snippet=_clean_snippet(snippet),
                    matched_in=_matches(matched_in),
                    score=round(float(score_value or 0), 6),
                    folder_path=paths.get(document.folder_id, ""),
                    department_name=department_name,
                    category_name=category_name,
                    tags=tags.get(document.id, []),
                )
            )
        return hits

    def _facets(self, criteria: list) -> SearchFacets:
        departments = self.session.execute(
            select(Department.id, Department.name, func.count(Document.id))
            .select_from(Document)
            .join(Department, Department.id == Document.department_id)
            .where(*criteria)
            .group_by(Department.id, Department.name)
            .order_by(func.count(Document.id).desc(), Department.name.asc())
        ).all()
        categories = self.session.execute(
            select(Category.id, Category.name, func.count(Document.id))
            .select_from(Document)
            .join(Category, Category.id == Document.category_id)
            .where(*criteria)
            .group_by(Category.id, Category.name)
            .order_by(func.count(Document.id).desc(), Category.name.asc())
        ).all()
        types = self.session.execute(
            select(Document.source_type, func.count(Document.id))
            .where(*criteria)
            .group_by(Document.source_type)
            .order_by(func.count(Document.id).desc(), Document.source_type.asc())
        ).all()
        tags = self.session.execute(
            select(Tag.id, Tag.name, func.count(Document.id))
            .select_from(Document)
            .join(DocumentTag, DocumentTag.document_id == Document.id)
            .join(Tag, Tag.id == DocumentTag.tag_id)
            .where(*criteria)
            .group_by(Tag.id, Tag.name)
            .order_by(func.count(Document.id).desc(), Tag.name.asc())
        ).all()
        return SearchFacets(
            department=[FacetBucket(id=str(row[0]), name=row[1], count=row[2]) for row in departments],
            category=[FacetBucket(id=str(row[0]), name=row[1], count=row[2]) for row in categories],
            type=[FacetBucket(id=_type_id(row[0]), name=_type_id(row[0]), count=row[1]) for row in types],
            tags=[FacetBucket(id=str(row[0]), name=row[1], count=row[2]) for row in tags],
        )

    def _log(self, principal: Principal, query: str, result_count: int) -> None:
        self.session.add(
            SearchLog(
                user_id=principal.user.id,
                query=query,
                result_count=result_count,
                channel=channel_for(principal),
            )
        )
        self.session.commit()


def refresh_search_vector(session: Session, document_id: UUID) -> None:
    from sqlalchemy import text

    session.execute(
        text("SELECT refresh_search_vector(CAST(:document_id AS uuid))"),
        {"document_id": document_id},
    )


def _bounded(params: SearchParams) -> SearchParams:
    query = params.q.strip()
    if len(query) > MAX_QUERY_LENGTH:
        raise ApiError(422, "QUERY_TOO_LONG", "Enter a search of 300 characters or fewer.")
    page = params.page if params.page >= 1 else 1
    page_size = params.page_size if params.page_size >= 1 else DEFAULT_PAGE_SIZE
    page_size = min(page_size, PAGE_SIZE_CAP)
    return replace(params, q=query, page=page, page_size=page_size)


def _regconfig():
    """regconfig, not varchar. websearch_to_tsquery rejects an uncast string."""
    return cast(literal("english"), REGCONFIG)


def _term(query: str):
    return cast(literal(query), Text)


def _tsquery(query: str):
    return func.websearch_to_tsquery(_regconfig(), _term(query))


def _text_predicate(query: str):
    """Full-text match, plus trigram word similarity for partials and typos.

    `name %>` and `original_filename %>` are the indexable pg_trgm operators.
    Similarity on those two columns is what lets "inven" find Inventory.
    """
    full_text = Document.search_vector.op("@@")(_tsquery(query))
    if len(query) < 3:
        return full_text
    return or_(
        full_text,
        Document.name.op("%>")(_term(query)),
        Document.original_filename.op("%>")(_term(query)),
    )


def _rank(query: str):
    if not query:
        return literal(0.0)
    tsq = _tsquery(query)
    return (
        func.coalesce(func.ts_rank_cd(Document.search_vector, tsq, 32), 0.0) * 4.0
        + func.coalesce(func.word_similarity(_term(query), Document.name), 0.0) * 3.0
        + func.coalesce(func.word_similarity(_term(query), Document.original_filename), 0.0)
    )


def _snippet(query: str):
    if not query:
        return func.left(func.coalesce(Document.description, Document.name, ""), 280)
    tsq = _tsquery(query)
    headline = func.ts_headline(
        _regconfig(),
        func.concat_ws(
            literal("\n"),
            Document.name,
            func.coalesce(Document.description, ""),
            func.coalesce(Document.content_text, ""),
        ),
        tsq,
        cast(literal(HEADLINE_OPTIONS), Text),
    )
    return case(
        (Document.search_vector.op("@@")(tsq), headline),
        else_=func.concat_ws(literal(" — "), Document.name, Document.original_filename),
    )


def _matched_in(query: str):
    if not query:
        return literal_column("ARRAY[]::text[]")
    tsq = _tsquery(query)
    fields = (
        ("name", _column_match(Document.name, query, tsq)),
        ("tag", _tag_match(query, tsq)),
        ("category", _category_match(query, tsq)),
        ("description", _column_match(Document.description, query, tsq)),
        ("content", _column_match(Document.content_text, query, tsq)),
    )
    return cast(
        func.array_remove(array([case((condition, literal(label))) for label, condition in fields]), None),
        ARRAY(Text),
    )


def _column_match(column, query: str, tsq):
    clauses = [func.to_tsvector(_regconfig(), func.coalesce(column, "")).op("@@")(tsq)]
    if len(query) >= 3:
        clauses.append(column.op("%>")(query))
    return or_(*clauses)


def _tag_match(query: str, tsq):
    # Correlate Document only. The hit query also joins categories, and a nested
    # select would otherwise lose its FROM clause.
    return exists(
        select(Tag.id)
        .join(DocumentTag, DocumentTag.tag_id == Tag.id)
        .where(DocumentTag.document_id == Document.id, _column_match(Tag.name, query, tsq))
        .correlate(Document)
    )


def _category_match(query: str, tsq):
    return exists(
        select(Category.id)
        .where(Category.id == Document.category_id, _column_match(Category.name, query, tsq))
        .correlate(Document)
    )


def _tags_for(session: Session, document_ids: list[UUID]) -> dict[UUID, list[Tag]]:
    grouped: dict[UUID, list[Tag]] = defaultdict(list)
    if not document_ids:
        return grouped
    rows = session.execute(
        select(DocumentTag.document_id, Tag)
        .join(Tag, Tag.id == DocumentTag.tag_id)
        .where(DocumentTag.document_id.in_(document_ids))
        .order_by(Tag.name.asc())
    ).all()
    for document_id, tag in rows:
        grouped[document_id].append(tag)
    return grouped


def _matches(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        inner = value.strip("{}")
        if not inner:
            return []
        return [part.strip().strip('"') for part in inner.split(",") if part.strip()]
    return [str(item) for item in value if item]


def _clean_snippet(value: str | None) -> str:
    if not value:
        return ""
    text = " ".join(value.split())
    if len(text) > 320:
        return text[:317].rstrip() + "..."
    return text


def _like_prefix(query: str) -> str:
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"{escaped}%"


def _type_id(source) -> str:
    return source.value if isinstance(source, SourceType) else str(source)
