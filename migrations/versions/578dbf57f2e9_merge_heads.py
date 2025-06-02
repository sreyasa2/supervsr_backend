"""merge heads

Revision ID: 578dbf57f2e9
Revises: 3b21325d3c22, add_type_column
Create Date: 2025-06-02 16:12:18.329753

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '578dbf57f2e9'
down_revision = ('3b21325d3c22', 'add_type_column')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
