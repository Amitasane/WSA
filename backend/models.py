from sqlalchemy import Column, Integer, String, Date, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.database import Base


# ================= USER MODEL =================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    first_name = Column(String)
    last_name = Column(String)

    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True)
    department = Column(String)

    hashed_password = Column(String)
    role = Column(String)

    records = relationship("Record", back_populates="owner")


# ================= RECORD MODEL =================

class Record(Base):
    __tablename__ = "records"

    id = Column(Integer, primary_key=True, index=True)

    # Professional Record Code (will generate in Phase 2)
    record_code = Column(String, unique=True, index=True)

    date = Column(Date)
    auditor_name = Column(String)
    shift = Column(String)
    line = Column(String)
    type = Column(String)
    parts_checked = Column(Integer)
    nok = Column(Integer)

    owner_id = Column(Integer, ForeignKey("users.id"))

    owner = relationship("User", back_populates="records")

    # Relationship to cases
    cases = relationship("Case", back_populates="record", cascade="all, delete")


# ================= CASE MODEL =================

class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)

    # Professional Case Code (will generate in Phase 3)
    case_code = Column(String, unique=True, index=True)

    record_id = Column(Integer, ForeignKey("records.id"))

    rejection_station = Column(String)
    particle_location = Column(String)
    body = Column(String)
    valve = Column(String)
    nozzle = Column(String)
    magnet = Column(String)

    remark = Column(Text)
    bin_number = Column(String)

    image1 = Column(String)
    image2 = Column(String)
    image3 = Column(String)

    created_at = Column(Date)

    record = relationship("Record", back_populates="cases")