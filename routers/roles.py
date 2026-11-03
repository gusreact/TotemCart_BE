from fastapi import APIRouter, Depends, HTTPException, status

from schemas.role_schema import RoleCreate, RoleOut, RoleUpdate
from services.role_service import RoleService
from services.security import require_admin


router = APIRouter(prefix="/api/roles", tags=["roles"])


@router.get("", response_model=list[RoleOut])
def get_roles(
    current_user: dict = Depends(require_admin),
    service: RoleService = Depends(),
):
    return service.get_all()


@router.get("/{role_id}", response_model=RoleOut)
def get_role(
    role_id: int,
    current_user: dict = Depends(require_admin),
    service: RoleService = Depends(),
):
    role = service.get_by_id(role_id)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rol no encontrado",
        )
    return role


@router.post("", response_model=RoleOut, status_code=status.HTTP_201_CREATED)
def create_role(
    payload: RoleCreate,
    current_user: dict = Depends(require_admin),
    service: RoleService = Depends(),
):
    return service.create(payload)


@router.put("/{role_id}", response_model=RoleOut)
def update_role(
    role_id: int,
    payload: RoleUpdate,
    current_user: dict = Depends(require_admin),
    service: RoleService = Depends(),
):
    return service.update(role_id, payload)


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(
    role_id: int,
    current_user: dict = Depends(require_admin),
    service: RoleService = Depends(),
):
    service.delete(role_id)
    return None
