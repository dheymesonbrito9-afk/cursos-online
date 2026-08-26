from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=6, max_length=100)

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class ProductIn(BaseModel):
    name: str
    description: str = ""
    price: float = Field(gt=0)
    sale_price: Optional[float] = None
    stock: int = Field(ge=0)
    image_url: str = ""
    sku: str
    category_id: Optional[int] = None
    featured: bool = False
    active: bool = True

class CategoryIn(BaseModel):
    name: str

class CartIn(BaseModel):
    product_id: int
    quantity: int = Field(ge=1, le=99)

class CheckoutIn(BaseModel):
    address: str = Field(min_length=5, max_length=300)
