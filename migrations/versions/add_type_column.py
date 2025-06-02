"""add type column

Revision ID: add_type_column
Revises: 
Create Date: 2024-05-29 18:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_type_column'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Add type column to ai_model table
    op.add_column('ai_model', sa.Column('type', sa.String(255), nullable=True))


def downgrade():
    # Remove type column from ai_model table
    op.drop_column('ai_model', 'type') 