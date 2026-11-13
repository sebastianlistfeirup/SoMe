"""Two-factor login (TOTP) for dashboard users. Additive and guarded like 0002."""

import sqlalchemy as sa
from alembic import op

from app.db.models import Base

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

COLUMNS = {
    "auth_users": [
        sa.Column("totp_secret_encrypted", sa.Text(), nullable=True),
        sa.Column("totp_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("totp_last_step", sa.Integer(), nullable=True),
        sa.Column("recovery_codes_json", sa.JSON(), nullable=True),
    ],
    "auth_sessions": [
        sa.Column("mfa_pending", sa.Boolean(), nullable=False, server_default=sa.false()),
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
