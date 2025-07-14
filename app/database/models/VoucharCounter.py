from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field, validator


class ResetFrequency(str, Enum):
    """How often the counter should reset."""
    NEVER = "never"
    YEARLY = "yearly"
    MONTHLY = "monthly"
    DAILY = "daily"  # handy if you ever need it


class VoucherCounter(BaseModel):
    """A counter for generating unique voucher numbers.
    This model tracks the current number, starting number, and reset logic.
    It is used to generate voucher numbers for sales, purchases, etc.
    """
    # core identifiers
    voucher_type: str = Field(..., description="e.g. 'Sales', 'Purchase'")
    company_id: str = Field(..., description="UUID of the company")
    user_id: str = Field(..., description="UUID of the user who created this counter")

    # formatting
    prefix: str = Field(
        default="", description="String prepended to the number, e.g. 'INV/'"
    )
    suffix: str = Field(default="", description="String appended, e.g. '/25'")
    separator: str = Field(
        default="/", description="String between prefix and number, e.g. '/'"
    )
    pad_length: int = Field(
        default=4, ge=1, le=12, description="Digits to left‑pad the number with"
    )

    # counter state
    starting_number: int = Field(default=1, ge=0, description="Value after each reset")
    current_number: int = Field(
        default=0, ge=0, description="Last number issued (auto‑incremented)"
    )

    # reset logic
    reset_frequency: ResetFrequency = Field(default=ResetFrequency.NEVER)
    last_reset: datetime = Field(default_factory=datetime.utcnow)

    # book‑keeping
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_deleted: bool = False

    # ───── Validators ────────────────────────────────────────────────────
    @validator("current_number")
    def current_not_below_start(cls, v, values):
        start = values.get("starting_number", 1)
        if v < start:
            raise ValueError("current_number cannot be less than starting_number")
        return v

    # ───── Helpers (optional) ────────────────────────────────────────────
    def next_visible_number(self) -> str:
        """
        Compute—but do not bump—the next number the user will see.
        Mirrors the logic you use in `reserve_next_voucher_number`.
        """
        next_num = self.current_number + 1
        padded = str(next_num).zfill(self.pad_length)
        if self.suffix != "":
            return f"{self.prefix}{self.separator}{padded}{self.separator}{self.suffix}"
        return f"{self.prefix}{self.separator}{padded}"

    def start_counter(self):
        """
        Initialize the counter to the starting number.
        This is useful for when the counter is first created.
        """
        self.current_number = self.starting_number
        self.last_reset = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def reset_if_needed(self):
        """Check if the counter needs to be reset based on the reset frequency.
        This method checks the last reset time against the current time
        and the reset frequency, and resets the counter if necessary.
        """
        if self.reset_frequency == ResetFrequency.NEVER:
            return

        now = datetime.utcnow()
        if self.reset_frequency == ResetFrequency.YEARLY:
            reset_time = self.last_reset.replace(year=now.year)
        elif self.reset_frequency == ResetFrequency.MONTHLY:
            reset_time = self.last_reset.replace(year=now.year, month=now.month)
        elif self.reset_frequency == ResetFrequency.DAILY:
            reset_time = self.last_reset.replace(
                year=now.year, month=now.month, day=now.day
            )

        if now >= reset_time:
            self.reset_counter()

    def reset_counter(self):
        """
        Reset the counter to the starting number.
        This is useful for manual resets or when the reset frequency is met.
        """
        self.current_number = self.starting_number
        self.last_reset = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def reserve_next_voucher_number(self) -> str:
        """
        Reserve the next voucher number and return it.
        This method increments the counter and returns the formatted number.
        """
        self.current_number += 1
        padded = str(self.current_number).zfill(self.pad_length)
        formatted_number = f"{self.prefix}{padded}{self.suffix}"
        self.updated_at = datetime.utcnow()
        return formatted_number

    def __str__(self):
        return f"VoucherCounter({self.voucher_type}, {self.company_id}, {self.next_visible_number()})"


class VoucherCounterDB(VoucherCounter):
    counter_id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
