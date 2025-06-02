"""add frequency column

Revision ID: add_frequency_column
Revises: add_sop_status
Create Date: 2024-03-19

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_frequency_column'
down_revision = 'add_sop_status'
branch_labels = None
depends_on = None

def upgrade():
    # Add frequency column with default value of 10
    op.add_column('sop', sa.Column('frequency', sa.Integer(), nullable=False, server_default='10'))

def downgrade():
    # Remove frequency column
    op.drop_column('sop', 'frequency') 