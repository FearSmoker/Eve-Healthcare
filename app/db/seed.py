"""Seed script to populate initial sample diagnostic centres, tests, and users."""

from sqlalchemy import select
from app.core.security import hash_password
from app.db.base import Base, SessionLocal, engine
from app.models.centre import CentreTest, DiagnosticCentre, DiagnosticTest
from app.models.user import User, UserRole


def seed_database() -> None:
    print("🌱 Initializing database schema...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        print("🌱 Seeding Users...")
        # 1. Admin User
        admin_email = "admin@evehealthcare.com"
        admin = db.execute(select(User).where(User.email == admin_email)).scalar_one_or_none()
        if not admin:
            admin = User(
                email=admin_email,
                password_hash=hash_password("AdminPass123!"),
                full_name="EVE System Administrator",
                phone="+919876543210",
                role=UserRole.ADMIN.value,
                is_active=True,
            )
            db.add(admin)
            print(f"   Created Admin: {admin_email} / AdminPass123!")

        # 2. Patient User
        patient_email = "patient@evehealthcare.com"
        patient = db.execute(select(User).where(User.email == patient_email)).scalar_one_or_none()
        if not patient:
            patient = User(
                email=patient_email,
                password_hash=hash_password("PatientPass123!"),
                full_name="Priya Sharma",
                phone="+919812345678",
                role=UserRole.PATIENT.value,
                is_active=True,
            )
            db.add(patient)
            print(f"   Created Patient: {patient_email} / PatientPass123!")

        db.commit()

        print("🌱 Seeding Diagnostic Tests...")
        tests_data = [
            {
                "name": "Complete Blood Count (CBC)",
                "code": "CBC",
                "category": "Pathology",
                "description": "Evaluates overall health and detects a wide range of disorders, including anemia and infection.",
                "preparation_instructions": "No specific fasting required.",
            },
            {
                "name": "Lipid Profile Panel",
                "code": "LIPID_PANEL",
                "category": "Pathology",
                "description": "Measures cholesterol, triglycerides, HDL, and LDL levels to assess cardiovascular risk.",
                "preparation_instructions": "10-12 hours overnight fasting mandatory.",
            },
            {
                "name": "Thyroid Profile (T3, T4, TSH)",
                "code": "THYROID_TOTAL",
                "category": "Endocrinology",
                "description": "Assesses thyroid gland function and hormone levels.",
                "preparation_instructions": "Morning blood sample preferred.",
            },
            {
                "name": "HbA1c (Glycated Hemoglobin)",
                "code": "HBA1C",
                "category": "Diabetes",
                "description": "Provides an average of blood sugar levels over the past 2 to 3 months.",
                "preparation_instructions": "No fasting required.",
            },
            {
                "name": "Vitamin D 25-Hydroxy",
                "code": "VIT_D",
                "category": "Biochemistry",
                "description": "Measures Vitamin D level in blood to monitor bone and immune health.",
                "preparation_instructions": "Standard routine blood test.",
            },
            {
                "name": "Ultrasound Whole Abdomen",
                "code": "USG_ABDOMEN",
                "category": "Radiology",
                "description": "High-frequency sound waves to visualize organs inside the abdomen.",
                "preparation_instructions": "6 hours fasting and full bladder required.",
            },
        ]

        test_records = {}
        for td in tests_data:
            test = db.execute(select(DiagnosticTest).where(DiagnosticTest.code == td["code"])).scalar_one_or_none()
            if not test:
                test = DiagnosticTest(**td, is_active=True)
                db.add(test)
                db.flush()
                print(f"   Added Test: {test.name} [{test.code}]")
            test_records[td["code"]] = test

        db.commit()

        print("🌱 Seeding Diagnostic Centres...")
        centres_data = [
            {
                "name": "EVE Central Diagnostic Lab",
                "address": "100 Feet Road, HAL 2nd Stage, Indiranagar",
                "city": "Bengaluru",
                "state": "Karnataka",
                "pincode": "560038",
                "contact_phone": "+918025251122",
            },
            {
                "name": "Apollo Diagnostics Koramangala",
                "address": "5th Block, Jyoti Nivas College Road",
                "city": "Bengaluru",
                "state": "Karnataka",
                "pincode": "560095",
                "contact_phone": "+918041412233",
            },
            {
                "name": "Metropolis Healthcare Bandra",
                "address": "Hill Road, Bandra West",
                "city": "Mumbai",
                "state": "Maharashtra",
                "pincode": "400050",
                "contact_phone": "+912226456789",
            },
            {
                "name": "SRL Diagnostics Connaught Place",
                "address": "Barakhamba Road, Connaught Place",
                "city": "New Delhi",
                "state": "Delhi",
                "pincode": "110001",
                "contact_phone": "+911143567890",
            },
        ]

        centre_records = []
        for cd in centres_data:
            centre = db.execute(select(DiagnosticCentre).where(DiagnosticCentre.name == cd["name"])).scalar_one_or_none()
            if not centre:
                centre = DiagnosticCentre(**cd, is_active=True)
                db.add(centre)
                db.flush()
                print(f"   Added Centre: {centre.name} ({centre.city})")
            centre_records.append(centre)

        db.commit()

        print("🌱 Linking Tests to Centres with Pricing (in Paise)...")
        # Prices in paise: 35000 paise = ₹350.00
        pricing_matrix = {
            "CBC": 35000,          # ₹350.00
            "LIPID_PANEL": 75000,  # ₹750.00
            "THYROID_TOTAL": 65000,# ₹650.00
            "HBA1C": 50000,        # ₹500.00
            "VIT_D": 120000,       # ₹1200.00
            "USG_ABDOMEN": 180000, # ₹1800.00
        }

        for centre in centre_records:
            for code, price in pricing_matrix.items():
                test = test_records[code]
                link = db.execute(
                    select(CentreTest).where(
                        CentreTest.centre_id == centre.id,
                        CentreTest.test_id == test.id,
                    )
                ).scalar_one_or_none()

                if not link:
                    link = CentreTest(
                        centre_id=centre.id,
                        test_id=test.id,
                        price_paise=price,
                        is_available=True,
                    )
                    db.add(link)

        db.commit()
        print("✅ Database seeding completed successfully!")
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
