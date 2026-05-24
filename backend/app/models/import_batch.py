from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class ImportBatch(SQLModel, table=True):
    __tablename__ = "import_batches"

    batch_id: UUID = Field(primary_key=True)
    step_name: Optional[str] = None
    status: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    params: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSONB))
    log_path: Optional[str] = None
