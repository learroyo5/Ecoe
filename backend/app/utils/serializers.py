"""Hand-curated dict serializers for endpoints that intentionally return a
shape different from the raw ORM model (as opposed to Pydantic
response_model, used where the ORM shape itself is the right response).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import AssessmentItem, AssessmentTool, MediaAsset


def serialize_assessment_tool(db: Session, tool_id: int | None) -> dict | None:
    if not tool_id:
        return None
    tool = db.get(AssessmentTool, tool_id)
    if not tool:
        return None
    items = db.scalars(
        select(AssessmentItem)
        .where(AssessmentItem.tool_id == tool.id)
        .order_by(AssessmentItem.order_index.asc(), AssessmentItem.id.asc())
    ).all()
    return {
        "id": tool.id,
        "name": tool.name,
        "tool_type": tool.tool_type,
        "max_score": tool.max_score,
        "free_observation": tool.free_observation,
        "items": [
            {
                "id": item.id,
                "label": item.label,
                "score_per_item": item.score_per_item,
                "order_index": item.order_index,
            }
            for item in items
        ],
    }


def serialize_media_asset(asset: MediaAsset) -> dict:
    return {
        "id": asset.id,
        "filename": asset.filename,
        "original_name": asset.original_name,
        "content_type": asset.content_type,
        "target_viewer": asset.target_viewer,
        "station_id": asset.station_id,
        "file_url": f"/api/media/file/{asset.id}",
    }
