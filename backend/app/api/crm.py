"""CRM endpoints for contacts, appointments, and call interactions."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.appointment import Appointment
from app.models.call_interaction import CallInteraction
from app.models.contact import Contact

router = APIRouter(prefix="/crm", tags=["crm"])


# Pydantic schemas
class ContactResponse(BaseModel):
    """Contact response schema."""

    id: int
    user_id: int
    first_name: str
    last_name: str | None
    email: str | None
    phone_number: str
    company_name: str | None
    status: str
    tags: str | None
    notes: str | None

    class Config:
        """Pydantic config."""

        from_attributes = True


class ContactCreate(BaseModel):
    """Contact creation schema."""

    first_name: str
    last_name: str | None = None
    email: str | None = None
    phone_number: str
    company_name: str | None = None
    status: str = "new"
    tags: str | None = None
    notes: str | None = None


@router.get("/contacts", response_model=list[ContactResponse])
async def list_contacts(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
) -> list[Contact]:
    """List all contacts (simplified - normally would filter by user_id)."""
    result = await db.execute(
        select(Contact).offset(skip).limit(limit).order_by(Contact.created_at.desc()),
    )
    return list(result.scalars().all())


@router.get("/contacts/{contact_id}", response_model=ContactResponse)
async def get_contact(
    contact_id: int,
    db: AsyncSession = Depends(get_db),
) -> Contact:
    """Get a single contact by ID."""
    result = await db.execute(select(Contact).where(Contact.id == contact_id))
    contact = result.scalar_one_or_none()
    if not contact:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


@router.post("/contacts", response_model=ContactResponse, status_code=201)
async def create_contact(
    contact_data: ContactCreate,
    db: AsyncSession = Depends(get_db),
) -> Contact:
    """Create a new contact (simplified - normally would get user_id from auth)."""
    contact = Contact(
        user_id=1,  # TODO: Get from authenticated user
        **contact_data.model_dump(),
    )
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return contact


@router.get("/stats")
async def get_crm_stats(db: AsyncSession = Depends(get_db)) -> dict[str, int]:
    """Get CRM statistics."""
    contacts_result = await db.execute(select(Contact))
    contacts_count = len(list(contacts_result.scalars().all()))

    appointments_result = await db.execute(select(Appointment))
    appointments_count = len(list(appointments_result.scalars().all()))

    calls_result = await db.execute(select(CallInteraction))
    calls_count = len(list(calls_result.scalars().all()))

    return {
        "total_contacts": contacts_count,
        "total_appointments": appointments_count,
        "total_calls": calls_count,
    }
