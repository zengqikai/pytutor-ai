"""
RAG 知识库管理 API
==================

管理员接口，用于管理知识文档和检索。

接口列表：
    POST   /api/v1/rag/documents     - 导入教学文档
    GET    /api/v1/rag/documents     - 文档列表
    GET    /api/v1/rag/documents/{id} - 文档详情（含 chunks）
    DELETE /api/v1/rag/documents/{id} - 删除文档
    POST   /api/v1/rag/search        - 检索知识库
    POST   /api/v1/rag/rebuild       - 重建索引
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.session import get_db
from app.models.rag import RAGChunk, RAGDocument
from app.models.user import User, UserRole
from app.schemas.rag import (
    RAGChunkResponse,
    RAGDocumentCreate,
    RAGDocumentResponse,
    RAGRetrievalRequest,
    RAGRetrievalResponse,
)
from app.security.dependencies import get_current_user, require_role
from app.services.rag_service import ingest_document, rebuild_index, retrieve_context

router = APIRouter()


# ==============================
# 文档管理（管理员）
# ==============================

@router.post("/documents", response_model=RAGDocumentResponse, status_code=201)
async def create_document(
    request: RAGDocumentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.INSTRUCTOR)),
):
    """导入一篇教学文档。自动切分为 chunk 并加入检索索引。"""
    doc = await ingest_document(
        db,
        title=request.title,
        content=request.content,
        difficulty=request.difficulty,
        concepts=request.concepts,
        source_type=request.source_type,
    )
    return RAGDocumentResponse(
        id=doc.id,
        title=doc.title,
        source_type=doc.source_type,
        difficulty=doc.difficulty,
        concepts=doc.concepts,
        is_active=doc.is_active,
        chunk_count=len(doc.chunks),
        created_at=doc.created_at,
    )


@router.get("/documents", response_model=list[RAGDocumentResponse])
async def list_documents(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.INSTRUCTOR)),
):
    """获取知识文档列表。"""
    result = await db.execute(
        select(RAGDocument)
        .order_by(RAGDocument.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    docs = result.scalars().all()

    return [
        RAGDocumentResponse(
            id=d.id,
            title=d.title,
            source_type=d.source_type,
            difficulty=d.difficulty,
            concepts=d.concepts,
            is_active=d.is_active,
            chunk_count=len(d.chunks),
            created_at=d.created_at,
        )
        for d in docs
    ]


@router.get("/documents/{document_id}")
async def get_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.INSTRUCTOR)),
):
    """获取文档详情，含所有 chunk。"""
    result = await db.execute(
        select(RAGDocument)
        .where(RAGDocument.id == document_id)
        .options(selectinload(RAGDocument.chunks))
    )
    doc = result.scalar_one_or_none()
    if not doc:
        return {"detail": "文档不存在"}

    return {
        "id": doc.id,
        "title": doc.title,
        "content": doc.content,
        "difficulty": doc.difficulty,
        "concepts": doc.concepts,
        "is_active": doc.is_active,
        "chunks": [
            RAGChunkResponse.model_validate(c)
            for c in sorted(doc.chunks, key=lambda x: x.chunk_index)
        ],
        "created_at": doc.created_at.isoformat(),
    }


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """删除文档及其所有 chunk。"""
    result = await db.execute(
        select(RAGDocument).where(RAGDocument.id == document_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        return {"detail": "文档不存在"}

    # 从检索索引中移除
    from app.rag.retriever import retriever
    for chunk in doc.chunks:
        retriever.remove_chunk(chunk.id)

    await db.delete(doc)
    await db.commit()
    return {"detail": "已删除", "document_id": document_id}


# ==============================
# 检索（所有角色）
# ==============================

@router.post("/search", response_model=RAGRetrievalResponse)
async def search_knowledge(
    request: RAGRetrievalRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """检索知识库。返回相关文档片段。"""
    return await retrieve_context(db, request)


# ==============================
# 索引维护
# ==============================

@router.post("/rebuild")
async def rebuild_search_index(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """重建内存检索索引（从数据库重新加载所有 chunk）。"""
    count = await rebuild_index(db)
    return {"detail": f"索引已重建", "chunk_count": count}
