"""Pre-registered experiments and operations columns.

Fresh databases get these columns from 0001 (which uses create_all on the
current models), so every add_column is guarded by an inspector check.
"""

import sqlalchemy as sa
from alembic import op

from app.db.models import Base

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

COLUMNS = {
    "experiments": [
        sa.Column("spec_json", sa.JSON(), nullable=True),
        sa.Column("spec_sha256", sa.String(64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision", sa.String(120), nullable=True),
    ],
}


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    inspector = sa.inspect(bind)
    for table, columns in COLUMNS.items():
        existing = {column["name"] for column in inspector.get_columns(table)}
        for column in columns:
            if column.name not in existing:
                op.add_column(table, column)


def downgrade() -> None:
    for table, columns in COLUMNS.items():
        with op.batch_alter_table(table) as batch:
            for column in columns:
                batch.drop_column(column.name)
