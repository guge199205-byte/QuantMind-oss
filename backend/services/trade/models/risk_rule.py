"""
Risk Rule Model
"""

from sqlalchemy import JSON, Boolean, Column, Integer, String

from .base import Base, TimestampMixin


class RiskRule(Base, TimestampMixin):
    """Risk control rules"""

    __tablename__ = "risk_rules"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Rule info
    rule_name = Column(String(100), nullable=False, unique=True, index=True)
    rule_type = Column(String(50), nullable=False, index=True)
    description = Column(String(500), nullable=True)

    # Status
    is_active = Column(Boolean, nullable=False, default=True, index=True)

    # Rule parameters (flexible JSON)
    parameters = Column(JSON, nullable=False, default=dict)

    # Scope
    applies_to_all = Column(Boolean, nullable=False, default=True)
    # List of user IDs if not applies_to_all
    user_ids = Column(JSON, nullable=True)

    # Priority (higher number = higher priority)
    priority = Column(Integer, nullable=False, default=0)

    def __repr__(self):
        return (
            f"<RiskRule(id={self.id}, name={self.rule_name}, "
            f"type={self.rule_type}, active={self.is_active})>"
        )
