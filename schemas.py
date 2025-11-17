from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List

# Lead collected from web forms or chatbot
class Lead(BaseModel):
    company: str
    name: str
    email: EmailStr
    phone: Optional[str] = None
    message: Optional[str] = None
    source: str = Field(default="webform")

# Items optionally attached to a Lead (kept inside lead doc in MVP)

class Contactmessage(BaseModel):
    company: str
    name: str
    email: EmailStr
    phone: Optional[str] = None
    topic: str = Field(default="Generale")
    message: str

class Componentitem(BaseModel):
    code: str
    brand: Optional[str] = None
    type: Optional[str] = None
    mount: Optional[str] = Field(default=None, description="SMD/PTH")
    package: Optional[str] = None
    notes: Optional[str] = None

class File(BaseModel):
    bucket: str = Field(default="uploads")
    filename: str
    content_type: Optional[str] = None
    size: int

# Note: collection names derive from lowercased class names
