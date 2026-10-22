"""收藏接口：攻略收藏夹的增删查（按登录用户隔离）"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import require_user
from app.store import add_favorite, delete_favorite, list_favorites

router = APIRouter(prefix="/api/favorites", tags=["favorites"])


class FavoriteRequest(BaseModel):
    title: str = ""
    content: str = Field(..., min_length=1)
    session_id: str = ""


@router.get("")
def get_favorites(username: str = Depends(require_user)):
    """当前用户的收藏列表"""
    return {"favorites": list_favorites(username=username)}


@router.post("")
def create_favorite(req: FavoriteRequest, username: str = Depends(require_user)):
    """收藏一条攻略（归属当前登录用户）"""
    if not req.content.strip():
        raise HTTPException(400, "收藏内容不能为空")
    item = add_favorite(req.title, req.content, req.session_id, username=username)
    return {"id": item["id"], "title": item["title"]}


@router.delete("/{fid}")
def remove_favorite(fid: str, username: str = Depends(require_user)):
    """删除自己的收藏（他人的收藏返回 404）"""
    if not delete_favorite(fid, username=username):
        raise HTTPException(404, "收藏不存在或无权删除")
    return {"ok": True}
