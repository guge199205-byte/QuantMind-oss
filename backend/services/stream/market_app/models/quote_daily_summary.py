from sqlalchemy import Column, DateTime, Float, Integer, String

from .base import Base


class QuoteDailySummary(Base):
    __tablename__ = "quote_daily_summaries"
    id = Column(Integer, primary_key=True)
