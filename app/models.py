from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    google_id = Column(String, unique=True, index=True, nullable=False)
    profile_picture = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    stories = relationship("Story", back_populates="user", cascade="all, delete-orphan")
    story_progress = relationship("StoryProgress", back_populates="user", cascade="all, delete-orphan")

class Story(Base):
    __tablename__ = "stories"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    theme = Column(String, nullable=False)  # adventure, space, ocean, forest, castle, magic, friendship, animals
    hero_name = Column(String, nullable=False)
    hero_age = Column(Integer, nullable=False)
    reading_time = Column(Float, nullable=False)  # in minutes
    special_request = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_interactive = Column(Integer, default=0)  # 0 for regular, 1 for interactive
    
    # Relationships
    user = relationship("User", back_populates="stories")
    pages = relationship("StoryPage", back_populates="story", cascade="all, delete-orphan", order_by="StoryPage.page_number")
    progress = relationship("StoryProgress", back_populates="story", cascade="all, delete-orphan")

class StoryPage(Base):
    __tablename__ = "story_pages"
    
    id = Column(Integer, primary_key=True, index=True)
    story_id = Column(Integer, ForeignKey("stories.id"), nullable=False)
    page_number = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    image_url = Column(String, nullable=True)
    choices = Column(JSON, nullable=True)  # For interactive stories: [{"text": "Go left", "next_page": 2}, ...]
    
    # Relationships
    story = relationship("Story", back_populates="pages")

class StoryProgress(Base):
    __tablename__ = "story_progress"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    story_id = Column(Integer, ForeignKey("stories.id"), nullable=False)
    current_page = Column(Integer, default=1)
    path_taken = Column(JSON, default=list)  # List of page numbers visited
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="story_progress")
    story = relationship("Story", back_populates="progress")