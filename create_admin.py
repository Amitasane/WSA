import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.database import SessionLocal, engine, Base
from backend.auth import create_user
from backend.models import User
import backend.main # to ensure models are imported and created

Base.metadata.create_all(bind=engine)

db = SessionLocal()

# Check if admin already exists
admin_user = db.query(User).filter(User.username == "admin").first()

if admin_user:
    print("Admin user already exists!")
    print("Username: admin")
else:
    error = create_user(
        db,
        first_name="Admin",
        last_name="User",
        username="admin",
        email="admin@bosch.com",
        password="AdminPassword123!",
        confirm_password="AdminPassword123!",
        department="QMM",
        role="admin"
    )

    if error:
        print(f"Error creating admin: {error}")
    else:
        print("Admin user successfully created!")
        print("Username: admin")
        print("Password: AdminPassword123!")

db.close()
