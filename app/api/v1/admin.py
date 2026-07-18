import logging
from fastapi import APIRouter, Depends, HTTPException, status, Cookie, Header
from sqlalchemy.orm import Session
import uuid

from app.database import get_db
from app.models.user import User
from app.utils.security import verify_jwt
from app.services.payment_reminder_service import run_payment_reminder_sweep

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/admin", tags=["Admin"])

def get_current_admin_user(
    access_token: str | None = Cookie(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db)
) -> User:
    token = access_token
    if not token and authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    payload = verify_jwt(token)
    if not payload or "user_id" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session token"
        )

    user = db.get(User, uuid.UUID(payload["user_id"]))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    if user.role != "SUPER_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Only SUPER_ADMIN can run admin tasks."
        )

    return user

@router.post("/payment-reminders/run", status_code=status.HTTP_200_OK)
async def run_payment_reminders(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Manually triggers the daily payment reminder sweep.
    """
    summary = await run_payment_reminder_sweep(db)
    return summary
