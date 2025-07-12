from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import app.models as models
import app.schemas as schemas
from app.database import get_db
from app.auth import get_current_user

router = APIRouter(prefix="/user", tags=["users"])

@router.get("/profile", response_model=schemas.User)
def get_profile(current_user: models.User = Depends(get_current_user)):
    return current_user