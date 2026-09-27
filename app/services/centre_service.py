import uuid
from typing import Optional, Sequence
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import EntityAlreadyExistsError, EntityNotFoundError
from app.models.centre import CentreTest, DiagnosticCentre, DiagnosticTest
from app.schemas.centre import (
    CentreTestLinkCreate,
    DiagnosticCentreCreate,
    DiagnosticTestCreate,
)


class CentreService:
    @staticmethod
    def create_centre(db: Session, request: DiagnosticCentreCreate) -> DiagnosticCentre:
        """Create a new diagnostic centre."""
        centre = DiagnosticCentre(
            name=request.name,
            address=request.address,
            city=request.city,
            state=request.state,
            pincode=request.pincode,
            contact_phone=request.contact_phone,
            is_active=True,
        )
        db.add(centre)
        db.commit()
        db.refresh(centre)
        return centre

    @staticmethod
    def get_centre_by_id(db: Session, centre_id: uuid.UUID) -> DiagnosticCentre:
        """Retrieve a diagnostic centre along with its available tests and pricing."""
        stmt = (
            select(DiagnosticCentre)
            .options(
                selectinload(DiagnosticCentre.centre_tests).selectinload(CentreTest.test)
            )
            .where(DiagnosticCentre.id == centre_id)
        )
        centre = db.execute(stmt).scalar_one_or_none()
        if not centre:
            raise EntityNotFoundError("Diagnostic Centre", centre_id)
        return centre

    @staticmethod
    def list_centres(
        db: Session,
        city: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[Sequence[DiagnosticCentre], int]:
        """List active diagnostic centres with optional filtering and pagination."""
        query = select(DiagnosticCentre).where(DiagnosticCentre.is_active.is_(True))

        if city:
            query = query.where(DiagnosticCentre.city.ilike(f"%{city.strip()}%"))
        if search:
            search_pattern = f"%{search.strip()}%"
            query = query.where(
                (DiagnosticCentre.name.ilike(search_pattern))
                | (DiagnosticCentre.address.ilike(search_pattern))
            )

        # Count total
        count_stmt = select(func.count()).select_from(query.subquery())
        total = db.execute(count_stmt).scalar_one()

        # Paginate
        offset = (page - 1) * page_size
        items = db.execute(
            query.order_by(DiagnosticCentre.name.asc()).offset(offset).limit(page_size)
        ).scalars().all()

        return items, total

    @staticmethod
    def create_test(db: Session, request: DiagnosticTestCreate) -> DiagnosticTest:
        """Create a new diagnostic test definition."""
        existing = db.execute(
            select(DiagnosticTest).where(DiagnosticTest.code == request.code.upper())
        ).scalar_one_or_none()

        if existing:
            raise EntityAlreadyExistsError("Diagnostic Test", "code", request.code.upper())

        test = DiagnosticTest(
            name=request.name,
            code=request.code.upper(),
            category=request.category,
            description=request.description,
            preparation_instructions=request.preparation_instructions,
            is_active=True,
        )
        db.add(test)
        db.commit()
        db.refresh(test)
        return test

    @staticmethod
    def list_tests(
        db: Session,
        category: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[Sequence[DiagnosticTest], int]:
        """List active diagnostic tests with optional search, category filter and pagination."""
        query = select(DiagnosticTest).where(DiagnosticTest.is_active.is_(True))

        if category:
            query = query.where(DiagnosticTest.category.ilike(f"%{category.strip()}%"))
        if search:
            search_pattern = f"%{search.strip()}%"
            query = query.where(
                (DiagnosticTest.name.ilike(search_pattern))
                | (DiagnosticTest.code.ilike(search_pattern))
            )

        count_stmt = select(func.count()).select_from(query.subquery())
        total = db.execute(count_stmt).scalar_one()

        offset = (page - 1) * page_size
        items = db.execute(
            query.order_by(DiagnosticTest.name.asc()).offset(offset).limit(page_size)
        ).scalars().all()

        return items, total

    @staticmethod
    def link_test_to_centre(
        db: Session, centre_id: uuid.UUID, request: CentreTestLinkCreate
    ) -> CentreTest:
        """Associate a diagnostic test with a centre and set its centre-specific price."""
        # Verify centre exists
        centre = db.execute(
            select(DiagnosticCentre).where(DiagnosticCentre.id == centre_id)
        ).scalar_one_or_none()
        if not centre:
            raise EntityNotFoundError("Diagnostic Centre", centre_id)

        # Verify test exists
        test = db.execute(
            select(DiagnosticTest).where(DiagnosticTest.id == request.test_id)
        ).scalar_one_or_none()
        if not test:
            raise EntityNotFoundError("Diagnostic Test", request.test_id)

        # Check if already linked
        existing = db.execute(
            select(CentreTest).where(
                CentreTest.centre_id == centre_id,
                CentreTest.test_id == request.test_id,
            )
        ).scalar_one_or_none()

        if existing:
            # Update price and availability
            existing.price_paise = request.price_paise
            existing.is_available = request.is_available
            db.commit()
            db.refresh(existing)
            return existing

        link = CentreTest(
            centre_id=centre_id,
            test_id=request.test_id,
            price_paise=request.price_paise,
            is_available=request.is_available,
        )
        db.add(link)
        db.commit()
        db.refresh(link)
        return link
