from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.clients import ClientCreate, ClientListResponse, ClientRead, ClientUpdate
from app.services.client_service import create_client, delete_client, get_client, list_clients, update_client


router = APIRouter(prefix="/api/clients", tags=["clients"])


@router.post("", response_model=ClientRead, status_code=status.HTTP_201_CREATED)
def create_client_endpoint(payload: ClientCreate, db: Session = Depends(get_db)) -> ClientRead:
    return create_client(db, payload)


@router.get("", response_model=ClientListResponse)
def list_clients_endpoint(
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> ClientListResponse:
    items, total = list_clients(db, limit=limit, offset=offset)
    return ClientListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{client_id}", response_model=ClientRead)
def get_client_endpoint(client_id: str, db: Session = Depends(get_db)) -> ClientRead:
    client = get_client(db, client_id)
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return client


@router.patch("/{client_id}", response_model=ClientRead)
def update_client_endpoint(client_id: str, payload: ClientUpdate, db: Session = Depends(get_db)) -> ClientRead:
    client = get_client(db, client_id)
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return update_client(db, client, payload)


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client_endpoint(client_id: str, db: Session = Depends(get_db)) -> Response:
    client = get_client(db, client_id)
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    delete_client(db, client)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
