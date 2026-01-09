from pydantic import BaseModel, EmailStr
from typing import Optional, List

class ConversationMessage(BaseModel):
    role: str
    content: str
    ts: Optional[float] = None
    
    class Config:
        extra = "ignore"

class ConversationSync(BaseModel):
    id: str
    title: str
    messages: List[ConversationMessage]
    
    class Config:
        extra = "ignore"

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: str

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str
    username: str

class ChangePassword(BaseModel):
    old_password: str
    new_password: str

class UserDetailResponse(BaseModel):
    id: int
    username: str
    email: str
    created_at: str
