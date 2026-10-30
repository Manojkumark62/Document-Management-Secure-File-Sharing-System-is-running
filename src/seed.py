from src.database import SessionLocal
import src.authentication.models
import src.documentation.models
from src.roles.models import Role


DEFAULT_ROLES = [
    {"name": "admin", "description": "Full administrative access"},
    {"name": "manager", "description": "Manages documents and sharing"},
    {"name": "user", "description": "Manages owned documents and sharing"},
    {"name": "viewer", "description": "Views and downloads accessible documents"},
]


def seed_roles():
    db = SessionLocal()

    try:
        for item in DEFAULT_ROLES:
            existing_role = db.query(Role).filter(Role.name == item["name"]).first()

            if not existing_role:
                db.add(Role(**item))

        db.commit()
        print("Default roles seeded successfully")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    seed_roles()