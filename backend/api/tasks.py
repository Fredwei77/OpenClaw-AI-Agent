from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def get_tasks():
    return {"message": "List of all tasks"}
