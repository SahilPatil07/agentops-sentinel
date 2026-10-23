from fastapi import APIRouter

from agentic_worker.domain.models import IncidentCreate, IncidentRecord
from agentic_worker.persistence.store import Store


def incident_routes(store: Store) -> APIRouter:
    router = APIRouter(prefix="/api/v1/incidents", tags=["incidents"])

    @router.post("", response_model=IncidentRecord, status_code=201)
    def create_incident(incident: IncidentCreate) -> IncidentRecord:
        return store.create_incident(incident)

    @router.get("/{incident_id}", response_model=IncidentRecord)
    def get_incident(incident_id: str) -> IncidentRecord:
        return store.get_incident(incident_id)

    return router
