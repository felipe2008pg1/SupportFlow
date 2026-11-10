from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.tokens import TokenError, decode_access_token
from app.db.session import get_db
from app.models.user import Role, User

_bearer = HTTPBearer(auto_error=False)


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise _unauthorized()
    try:
        user_id = decode_access_token(creds.credentials)
    except TokenError:
        raise _unauthorized() from None
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise _unauthorized()
    return user


def require_roles(*roles: Role) -> Callable[[User], User]:
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return user

    return checker
