"""add sop status

Revision ID: add_sop_status
Revises: 
Create Date: 2024-05-29 18:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_sop_status'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Add status column to sop table with default value 'draft'
    op.add_column('sop', sa.Column('status', sa.String(50), nullable=False, server_default='draft'))


def downgrade():
    # Remove status column from sop table
    op.drop_column('sop', 'status') 