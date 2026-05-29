from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from backend.services.api.models.base import Base


class ModelRecord(Base):
    """AI模型记录表"""

    __tablename__ = "admin_models"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(64), nullable=False, index=True, default="default")
    user_id = Column(String(64), nullable=False, index=True, comment="归属用户ID")
    name = Column(String(128), nullable=False, index=True)
    description = Column(Text, nullable=True)
    source_type = Column(String(32), nullable=False, default="ai_model", comment="ai_model, hybrid, external")
    start_date = Column(DateTime, nullable=True, comment="模型数据开始日期")
    end_date = Column(DateTime, nullable=True, comment="模型数据结束日期")
    config = Column(JSON, nullable=True, comment="配置参数")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    files = relationship("DataFileRecord", back_populates="model", cascade="all, delete-orphan")


class DataFileRecord(Base):
    """数据文件记录表"""

    __tablename__ = "admin_data_files"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(64), nullable=False, index=True, default="default")
    data_source_id = Column(Integer, ForeignKey("admin_models.id", ondelete="CASCADE"))
    filename = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=True)
    status = Column(String(32), default="uploaded", comment="uploaded, processing, ready, error")
    meta = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    model = relationship("ModelRecord", back_populates="files")


class TrainingJobRecord(Base):
    """模型云端训练任务记录表"""

    __tablename__ = "admin_training_jobs"

    id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), nullable=False, index=True, default="default")
    user_id = Column(String(64), nullable=False, index=True)
    status = Column(
        String(32),
        default="pending",
        comment="pending, provisioning, running, waiting_callback, completed, failed",
    )
    instance_id = Column(String(64), nullable=True, comment="云服务器ID")
    request_payload = Column(JSON, nullable=True, comment="前端请求参数")
    logs = Column(Text, nullable=True, comment="任务日志(或COS链接)")
    result = Column(JSON, nullable=True, comment="训练结果与指标")
    progress = Column(Integer, default=0, comment="进度百分比 0-100")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
