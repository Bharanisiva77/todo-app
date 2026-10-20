from datetime import date
from pydantic import BaseModel, Field, ConfigDict, EmailStr, field_validator

STATUSES = {"Pending", "In Progress", "Completed"}
PRIORITIES = {"Low", "Medium", "High", "Urgent"}

class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_.-]+$")
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=128)

class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=5000)
    status: str = "Pending"
    priority: str = "Medium"
    tags: str = Field(default="", max_length=300)
    due_date: date | None = None

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value):
        if not value.strip():
            raise ValueError("Title cannot be blank.")
        return value.strip()

    @field_validator("status")
    @classmethod
    def valid_status(cls, value):
        if value not in STATUSES:
            raise ValueError("Status must be Pending, In Progress, or Completed.")
        return value

    @field_validator("priority")
    @classmethod
    def valid_priority(cls, value):
        if value not in PRIORITIES:
            raise ValueError("Priority must be Low, Medium, High, or Urgent.")
        return value

class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    description: str
    status: str
    priority: str
    tags: str
    due_date: date | None
