from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def get_leads():
    return {"message": "List of all leads"}
