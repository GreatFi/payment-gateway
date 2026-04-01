from sqlalchemy import Float, Integer, String, create_engine, DateTime
from sqlalchemy.orm import *
from sqlalchemy.sql import func
import os
import dotenv

dotenv.load_dotenv()

engine = create_engine(os.environ.get("db"))

class Base(DeclarativeBase):
    pass


class Payment(Base):

    __tablename__ = 'Payments'

    id:Mapped[int] = mapped_column(primary_key=True)
    order_id:Mapped[int] = mapped_column(Integer, nullable=False) 
    customer_id:Mapped[int] = mapped_column(Integer, nullable=False) 
    amount:Mapped[float] = mapped_column(Float, nullable=False)
    currency : Mapped[str] = mapped_column(String(10), nullable=False)
    payment_intent_id :Mapped[str] = mapped_column(String(50), nullable=True)
    status:Mapped[str] = mapped_column(String(30), nullable=False, default='pending')
    created_at:Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())
    authorized_at:Mapped[str] = mapped_column(DateTime(timezone=True), nullable=True)
    succeeded_at:Mapped[str] = mapped_column(DateTime(timezone=True), nullable=True)
    refunded_at :Mapped[str] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at:Mapped[str] = mapped_column(DateTime(timezone=True), nullable=True)