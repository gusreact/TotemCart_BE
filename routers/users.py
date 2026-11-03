from fastapi import APIRouter, Depends, HTTPException, status

from schemas.user_schema import UserCreate, UserOut, UserUpdate
from services.user_service import UserService
from services.security import require_admin

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def get_all_users(
    current_user: dict = Depends(require_admin),
    service: UserService = Depends(),
):
    return service.get_all_users()


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    current_user: dict = Depends(require_admin),
    service: UserService = Depends(),
):
    return service.create_user(payload)


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    current_user: dict = Depends(require_admin),
    service: UserService = Depends(),
):
    return service.update_user(user_id, payload)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    current_user: dict = Depends(require_admin),
    service: UserService = Depends(),
):
    service.delete_user(user_id)
    return None
