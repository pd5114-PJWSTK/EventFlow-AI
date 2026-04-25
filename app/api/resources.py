from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.resources import (
    EquipmentCreate,
    EquipmentListResponse,
    EquipmentRead,
    EquipmentTypeCreate,
    EquipmentTypeListResponse,
    EquipmentTypeRead,
    EquipmentUpdate,
    PersonCreate,
    PersonListResponse,
    PersonRead,
    PersonSkillAssign,
    PersonSkillRead,
    PersonUpdate,
    SkillCreate,
    SkillListResponse,
    SkillRead,
    VehicleCreate,
    VehicleListResponse,
    VehicleRead,
    VehicleUpdate,
)
from app.services.resource_service import (
    ResourceValidationError,
    assign_skill_to_person,
    create_equipment,
    create_equipment_type,
    create_person,
    create_skill,
    create_vehicle,
    delete_equipment,
    delete_person,
    delete_vehicle,
    get_equipment,
    get_equipment_type,
    get_person,
    get_skill,
    get_vehicle,
    list_equipment,
    list_equipment_types,
    list_people,
    list_skills,
    list_vehicles,
    update_equipment,
    update_person,
    update_vehicle,
)


router = APIRouter(prefix="/api/resources", tags=["resources"])


def _bad_request(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/skills", response_model=SkillRead, status_code=status.HTTP_201_CREATED)
def create_skill_endpoint(payload: SkillCreate, db: Session = Depends(get_db)) -> SkillRead:
    try:
        return create_skill(db, payload)
    except IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Skill already exists") from exc


@router.get("/skills", response_model=SkillListResponse)
def list_skills_endpoint(
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> SkillListResponse:
    items, total = list_skills(db, limit=limit, offset=offset)
    return SkillListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/skills/{skill_id}", response_model=SkillRead)
def get_skill_endpoint(skill_id: str, db: Session = Depends(get_db)) -> SkillRead:
    skill = get_skill(db, skill_id)
    if skill is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")
    return skill


@router.post("/people", response_model=PersonRead, status_code=status.HTTP_201_CREATED)
def create_person_endpoint(payload: PersonCreate, db: Session = Depends(get_db)) -> PersonRead:
    try:
        return create_person(db, payload)
    except ResourceValidationError as exc:
        raise _bad_request(exc) from exc


@router.get("/people", response_model=PersonListResponse)
def list_people_endpoint(
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> PersonListResponse:
    items, total = list_people(db, limit=limit, offset=offset)
    return PersonListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/people/{person_id}", response_model=PersonRead)
def get_person_endpoint(person_id: str, db: Session = Depends(get_db)) -> PersonRead:
    person = get_person(db, person_id)
    if person is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")
    return person


@router.patch("/people/{person_id}", response_model=PersonRead)
def update_person_endpoint(person_id: str, payload: PersonUpdate, db: Session = Depends(get_db)) -> PersonRead:
    person = get_person(db, person_id)
    if person is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")
    try:
        return update_person(db, person, payload)
    except ResourceValidationError as exc:
        raise _bad_request(exc) from exc


@router.delete("/people/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_person_endpoint(person_id: str, db: Session = Depends(get_db)) -> Response:
    person = get_person(db, person_id)
    if person is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")
    delete_person(db, person)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/people/{person_id}/skills", response_model=PersonSkillRead)
def assign_person_skill_endpoint(
    person_id: str,
    payload: PersonSkillAssign,
    db: Session = Depends(get_db),
) -> PersonSkillRead:
    person = get_person(db, person_id)
    if person is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")
    try:
        return assign_skill_to_person(db, person, payload)
    except ResourceValidationError as exc:
        raise _bad_request(exc) from exc


@router.post("/equipment-types", response_model=EquipmentTypeRead, status_code=status.HTTP_201_CREATED)
def create_equipment_type_endpoint(payload: EquipmentTypeCreate, db: Session = Depends(get_db)) -> EquipmentTypeRead:
    try:
        return create_equipment_type(db, payload)
    except IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Equipment type already exists") from exc


@router.get("/equipment-types", response_model=EquipmentTypeListResponse)
def list_equipment_types_endpoint(
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> EquipmentTypeListResponse:
    items, total = list_equipment_types(db, limit=limit, offset=offset)
    return EquipmentTypeListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/equipment-types/{equipment_type_id}", response_model=EquipmentTypeRead)
def get_equipment_type_endpoint(equipment_type_id: str, db: Session = Depends(get_db)) -> EquipmentTypeRead:
    item = get_equipment_type(db, equipment_type_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Equipment type not found")
    return item


@router.post("/equipment", response_model=EquipmentRead, status_code=status.HTTP_201_CREATED)
def create_equipment_endpoint(payload: EquipmentCreate, db: Session = Depends(get_db)) -> EquipmentRead:
    try:
        return create_equipment(db, payload)
    except ResourceValidationError as exc:
        raise _bad_request(exc) from exc
    except IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Equipment conflict") from exc


@router.get("/equipment", response_model=EquipmentListResponse)
def list_equipment_endpoint(
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> EquipmentListResponse:
    items, total = list_equipment(db, limit=limit, offset=offset)
    return EquipmentListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/equipment/{equipment_id}", response_model=EquipmentRead)
def get_equipment_endpoint(equipment_id: str, db: Session = Depends(get_db)) -> EquipmentRead:
    equipment = get_equipment(db, equipment_id)
    if equipment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Equipment not found")
    return equipment


@router.patch("/equipment/{equipment_id}", response_model=EquipmentRead)
def update_equipment_endpoint(
    equipment_id: str,
    payload: EquipmentUpdate,
    db: Session = Depends(get_db),
) -> EquipmentRead:
    equipment = get_equipment(db, equipment_id)
    if equipment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Equipment not found")
    try:
        return update_equipment(db, equipment, payload)
    except ResourceValidationError as exc:
        raise _bad_request(exc) from exc
    except IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Equipment conflict") from exc


@router.delete("/equipment/{equipment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_equipment_endpoint(equipment_id: str, db: Session = Depends(get_db)) -> Response:
    equipment = get_equipment(db, equipment_id)
    if equipment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Equipment not found")
    delete_equipment(db, equipment)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/vehicles", response_model=VehicleRead, status_code=status.HTTP_201_CREATED)
def create_vehicle_endpoint(payload: VehicleCreate, db: Session = Depends(get_db)) -> VehicleRead:
    try:
        return create_vehicle(db, payload)
    except ResourceValidationError as exc:
        raise _bad_request(exc) from exc
    except IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Vehicle conflict") from exc


@router.get("/vehicles", response_model=VehicleListResponse)
def list_vehicles_endpoint(
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> VehicleListResponse:
    items, total = list_vehicles(db, limit=limit, offset=offset)
    return VehicleListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/vehicles/{vehicle_id}", response_model=VehicleRead)
def get_vehicle_endpoint(vehicle_id: str, db: Session = Depends(get_db)) -> VehicleRead:
    vehicle = get_vehicle(db, vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
    return vehicle


@router.patch("/vehicles/{vehicle_id}", response_model=VehicleRead)
def update_vehicle_endpoint(vehicle_id: str, payload: VehicleUpdate, db: Session = Depends(get_db)) -> VehicleRead:
    vehicle = get_vehicle(db, vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
    try:
        return update_vehicle(db, vehicle, payload)
    except ResourceValidationError as exc:
        raise _bad_request(exc) from exc
    except IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Vehicle conflict") from exc


@router.delete("/vehicles/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vehicle_endpoint(vehicle_id: str, db: Session = Depends(get_db)) -> Response:
    vehicle = get_vehicle(db, vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
    delete_vehicle(db, vehicle)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
