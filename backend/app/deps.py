from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.services.checkout import CheckoutError, ShortageError


def get_db(request: Request):
    session_factory = request.app.state.SessionLocal
    db: Session = session_factory()
    try:
        yield db
    finally:
        db.close()


def shopper_id_from_request(request: Request) -> int:
    sid = request.session.get("shopper_id")
    if not sid:
        raise HTTPException(status_code=401, detail="Identify yourself to shop (name and phone)")
    return int(sid)


def raise_checkout(err: Exception) -> None:
    if isinstance(err, ShortageError):
        raise HTTPException(
            status_code=409,
            detail={"message": "Insufficient stock", "shortages": err.shortages},
        )
    if isinstance(err, CheckoutError):
        raise HTTPException(status_code=err.status_code, detail=err.message)
    raise err
