"""Initial migration - create all tables

Revision ID: 001_initial_migration
Revises: 
Create Date: 2025-06-30 22:56:28.012236

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision: str = '001_initial_migration'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create users table
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('google_id', sa.String(), nullable=False),
        sa.Column('profile_picture', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_google_id'), 'users', ['google_id'], unique=True)
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    
    # Create stories table
    op.create_table('stories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('theme', sa.String(), nullable=False),
        sa.Column('hero_name', sa.String(), nullable=False),
        sa.Column('hero_age', sa.Integer(), nullable=False),
        sa.Column('reading_time', sa.Float(), nullable=False),
        sa.Column('special_request', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('is_interactive', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_stories_id'), 'stories', ['id'], unique=False)
    
    # Create story_pages table
    op.create_table('story_pages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('story_id', sa.Integer(), nullable=False),
        sa.Column('page_number', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('image_url', sa.String(), nullable=True),
        sa.Column('choices', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['story_id'], ['stories.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_story_pages_id'), 'story_pages', ['id'], unique=False)
    
    # Create story_progress table
    op.create_table('story_progress',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('story_id', sa.Integer(), nullable=False),
        sa.Column('current_page', sa.Integer(), nullable=True),
        sa.Column('path_taken', sa.JSON(), nullable=True),
        sa.Column('last_updated', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['story_id'], ['stories.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_story_progress_id'), 'story_progress', ['id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_story_progress_id'), table_name='story_progress')
    op.drop_table('story_progress')
    op.drop_index(op.f('ix_story_pages_id'), table_name='story_pages')
    op.drop_table('story_pages')
    op.drop_index(op.f('ix_stories_id'), table_name='stories')
    op.drop_table('stories')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_index(op.f('ix_users_google_id'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')