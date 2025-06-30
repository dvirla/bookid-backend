from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict
from datetime import datetime

# Auth schemas
class GoogleAuthRequest(BaseModel):
    id_token: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    email: Optional[str] = None

# User schemas
class UserBase(BaseModel):
    email: EmailStr
    name: str

class UserCreate(UserBase):
    google_id: str
    profile_picture: Optional[str] = None

class User(UserBase):
    id: int
    profile_picture: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

# Story schemas
class StoryBase(BaseModel):
    title: str
    theme: str = Field(..., pattern="^(adventure|space|ocean|forest|castle|magic|friendship|animals)$")
    hero_name: str = Field(..., min_length=1, max_length=50)
    hero_age: int = Field(..., ge=2, le=12)
    reading_time: float = Field(..., ge=3, le=10)
    special_request: Optional[str] = Field(None, max_length=200)
    is_interactive: bool = False

class StoryCreate(BaseModel):
    theme: str = Field(..., pattern="^(adventure|space|ocean|forest|castle|magic|friendship|animals)$")
    hero_name: str = Field(..., min_length=1, max_length=50)
    hero_age: int = Field(..., ge=2, le=12)
    reading_time: float = Field(..., ge=3.0, le=10.0)
    special_request: Optional[str] = Field(None, max_length=200)
    is_interactive: bool = False
    
    class Config:
        str_strip_whitespace = True

class StoryChoice(BaseModel):
    text: str
    next_page: int

class StoryPage(BaseModel):
    id: int
    page_number: int
    text: str
    image_url: Optional[str]
    choices: Optional[List[StoryChoice]]
    
    class Config:
        from_attributes = True

class Story(StoryBase):
    id: int
    user_id: int
    created_at: datetime
    pages: List[StoryPage] = []
    
    class Config:
        from_attributes = True

class StoryList(BaseModel):
    id: int
    title: str
    theme: str
    hero_name: str
    created_at: datetime
    is_interactive: bool
    
    class Config:
        from_attributes = True

# Progress schemas
class StoryProgressUpdate(BaseModel):
    current_page: int
    choice_made: Optional[int] = None

class StoryProgress(BaseModel):
    current_page: int
    path_taken: List[int]
    last_updated: datetime
    
    class Config:
        from_attributes = True

# Share schemas
class StoryShare(BaseModel):
    share_url: str
    story_id: int