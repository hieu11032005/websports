"""Add source_url to Article model

Revision ID: 122c722cf1a8
Revises: e30262094f9d
Create Date: 2025-06-08 20:03:06.465040

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '122c722cf1a8'
down_revision = 'e30262094f9d'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('articles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('source_url', sa.String(length=500), nullable=True))
        batch_op.create_unique_constraint(None, ['source_url'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('articles', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='unique')
        batch_op.drop_column('source_url')

    # ### end Alembic commands ###
