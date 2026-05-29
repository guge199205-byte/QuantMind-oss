"""AI Strategy Service - 股票池文件数据库模型"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String, Text, Integer, Boolean


def _utcnow():
    return datetime.now(timezone.utc)


def _create_stock_pool_file_model(Base):
    """创建 StockPoolFile SQLAlchemy 模型"""

    class StockPoolFile(Base):
        __tablename__ = "stock_pool_files"

        id = Column(Integer, primary_key=True, autoincrement=True)
        tenant_id = Column(String(50), nullable=True, server_default="default")
        user_id = Column(String(50), nullable=False, index=True)
        pool_name = Column(String(200), nullable=True)
        session_id = Column(String(100), nullable=True)
        file_key = Column(String(500), nullable=False)
        file_url = Column(String(1000), nullable=True)
        relative_path = Column(String(500), nullable=True)
        format = Column(String(10), server_default="csv")
        file_size = Column(Integer, nullable=True)
        code_hash = Column(String(64), nullable=True)
        stock_count = Column(Integer, nullable=True)
        is_active = Column(Boolean, server_default="true")
        created_at = Column(DateTime, server_default="now()")
        updated_at = Column(DateTime, server_default="now()")

        def to_dict(self):
            return {
                "id": str(self.id),
                "tenant_id": self.tenant_id,
                "user_id": self.user_id,
                "pool_name": self.pool_name,
                "session_id": self.session_id,
                "file_key": self.file_key,
                "file_url": self.file_url,
                "relative_path": self.relative_path,
                "format": self.format,
                "file_size": self.file_size,
                "code_hash": self.code_hash,
                "stock_count": self.stock_count,
                "is_active": self.is_active,
                "created_at": self.created_at.isoformat() if self.created_at else None,
                "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            }

    return StockPoolFile


# 尝试使用已有的 SQLAlchemy Base，否则创建一个
try:
    from backend.shared.database_pool import Base as _SharedBase
except ImportError:
    try:
        from shared.database_pool import Base as _SharedBase
    except ImportError:
        from sqlalchemy.orm import declarative_base
        _SharedBase = declarative_base()

StockPoolFile = _create_stock_pool_file_model(_SharedBase)
