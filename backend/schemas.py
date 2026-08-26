from pydantic import BaseModel, EmailStr, ConfigDict

class RegisterIn(BaseModel):
    name: str
    email: EmailStr
    password: str

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class CourseIn(BaseModel):
    title: str
    description: str = ""
    image: str = ""
    price: int = 0

class LessonIn(BaseModel):
    title: str
    content: str = ""
    video_url: str = ""
    position: int = 1

class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    is_admin: bool
    model_config = ConfigDict(from_attributes=True)
