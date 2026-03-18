from fastapi import APIRouter, UploadFile, File
import tempfile
import os

from svg.parser import parse_svg
from nesting.placement import BottomLeftPlacer
from .models import NestResponse, PlacedPartResponse

router = APIRouter()


@router.post("/nest", response_model=NestResponse)
async def nest_svg(
    sheet_width: float,
    sheet_height: float,
    file: UploadFile = File(...)
):

    # сохраняем временный svg
    with tempfile.NamedTemporaryFile(delete=False, suffix=".svg") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:

        # парсим svg
        parts = parse_svg(tmp_path)

        # создаём placer
        placer = BottomLeftPlacer(
            sheet_width=sheet_width,
            sheet_height=sheet_height,
            allowed_angles=[0, 90]
        )

        # считаем раскрой
        layout = placer.place(parts)

        response_parts = []

        for p in layout:
            response_parts.append(
                PlacedPartResponse(
                    id=p.part_id,
                    x=p.x,
                    y=p.y,
                    angle=p.angle,
                    polygon=[[x, y] for x, y in p.polygon]
                )
            )

        return NestResponse(parts=response_parts)

    finally:
        os.remove(tmp_path)