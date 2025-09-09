from pydantic import BaseModel
from typing import Optional

class ProductInfo(BaseModel):
    url: str
    title: Optional[str] = None
    price: Optional[int] = None
    currency: str = "₽"
    error: Optional[str] = None
    captcha_rate: float = 0.0  # Для будущего планировщика

    class Config:
        extra = "allow"