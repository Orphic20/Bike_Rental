import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlmodel import SQLModel, Field
from sqlalchemy import Column, Computed, DateTime, ForeignKey, Numeric, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.types import TypeDecorator


def timestamp_column(*, nullable: bool = False) -> Column:
    """A timestamptz column the database fills in via now()."""
    return Column(
        DateTime(timezone=True), server_default=func.now(), nullable=nullable
    )


class EnumText(TypeDecorator):
    """A `text` column whose allowed values are pinned by a CHECK constraint.

    The database stores plain text, so this stores the enum's *value* rather
    than letting SQLAlchemy assume a native Postgres enum type exists.
    """

    impl = Text
    cache_ok = True

    def __init__(self, enum_class: type[Enum]):
        super().__init__()
        self.enum_class = enum_class

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return self.enum_class(value).value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return self.enum_class(value)


# =========================================================
# Enums — mirror every CHECK constraint exactly
# =========================================================
class RoleName(str, Enum):
    customer = "customer"
    staff = "staff"
    admin = "admin"


class BikeType(str, Enum):
    japanese = "japanese"
    folding = "folding"
    mountain = "mountain"


class BikeStatus(str, Enum):
    available = "available"
    rented = "rented"
    maintenance = "maintenance"
    retired = "retired"


class PaymentMethod(str, Enum):
    gcash = "gcash"
    cash = "cash"


class PaymentStatus(str, Enum):
    pending_verification = "pending_verification"
    unpaid_pending_pickup = "unpaid_pending_pickup"
    paid = "paid"
    refunded = "refunded"
    cancelled = "cancelled"
    rejected = "rejected"


class RateSelected(str, Enum):
    daily = "daily"
    weekly = "weekly"


class BookingType(str, Enum):
    new = "new"
    extension = "extension"


class RentalStatus(str, Enum):
    reserved = "reserved"
    active = "active"
    overdue = "overdue"
    returned = "returned"
    cancelled = "cancelled"
    no_show = "no_show"


class SwapStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    completed = "completed"


# =========================================================
# roles
# =========================================================
class Role(SQLModel, table=True):
    __tablename__ = "roles"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True),
    )
    name: RoleName = Field(sa_column=Column(EnumText(RoleName), nullable=False))


# =========================================================
# users
# =========================================================
class User(SQLModel, table=True):
    __tablename__ = "users"

    # matches auth.users.id — populated by the on_auth_user_created trigger,
    # never inserted directly by FastAPI.
    id: uuid.UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), primary_key=True))
    email: str
    google_id: Optional[str] = None
    name: str
    role_id: uuid.UUID = Field(foreign_key="roles.id")
    created_at: Optional[datetime] = Field(default=None, sa_column=timestamp_column())
    name_confirmed: bool = Field(default=False)
    tos_version_accepted: Optional[str] = None
    tos_accepted_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    is_active: bool = Field(default=True)


# =========================================================
# bikes
# =========================================================
class Bike(SQLModel, table=True):
    __tablename__ = "bikes"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True),
    )
    name: str
    type: BikeType = Field(sa_column=Column(EnumText(BikeType), nullable=False))
    status: BikeStatus = Field(
        default=BikeStatus.available,
        sa_column=Column(EnumText(BikeStatus), nullable=False),
    )
    daily_rate: Decimal = Field(sa_column=Column(Numeric(10, 2), nullable=False))
    weekly_rate: Optional[Decimal] = Field(
        default=None, sa_column=Column(Numeric(10, 2))
    )
    image_url: Optional[str] = None
    created_at: Optional[datetime] = Field(default=None, sa_column=timestamp_column())
    updated_at: Optional[datetime] = Field(default=None, sa_column=timestamp_column())


# =========================================================
# bookings — 1 row per transaction
# =========================================================
class Booking(SQLModel, table=True):
    __tablename__ = "bookings"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True),
    )
    user_id: uuid.UUID = Field(foreign_key="users.id")

    total_price: Decimal = Field(sa_column=Column(Numeric(10, 2), nullable=False))
    amount_paid: Decimal = Field(
        default=Decimal("0"), sa_column=Column(Numeric(10, 2), nullable=False)
    )
    # GENERATED ALWAYS in Postgres. Computed() keeps SQLAlchemy from emitting it
    # in INSERT/UPDATE, which Postgres rejects outright.
    balance_due: Optional[Decimal] = Field(
        default=None,
        sa_column=Column(
            Numeric(10, 2),
            Computed("total_price - amount_paid", persisted=True),
            nullable=False,
        ),
    )

    payment_method: PaymentMethod = Field(
        sa_column=Column(EnumText(PaymentMethod), nullable=False)
    )
    payment_status: PaymentStatus = Field(
        sa_column=Column(EnumText(PaymentStatus), nullable=False)
    )
    gcash_ref_no: Optional[str] = None
    gcash_receipt_url: Optional[str] = None

    expected_pickup_date: date
    rate_selected: RateSelected = Field(
        sa_column=Column(EnumText(RateSelected), nullable=False)
    )
    booking_type: BookingType = Field(
        default=BookingType.new,
        sa_column=Column(EnumText(BookingType), nullable=False),
    )
    parent_booking_id: Optional[uuid.UUID] = Field(
        default=None, foreign_key="bookings.id"
    )
    # bookings and rentals reference each other, so this side is use_alter to keep
    # SQLAlchemy from warning about an unresolvable cycle when it sorts tables.
    rental_id: Optional[uuid.UUID] = Field(
        default=None,
        sa_column=Column(
            PG_UUID(as_uuid=True), ForeignKey("rentals.id", use_alter=True)
        ),
    )

    waiver_version: Optional[str] = None
    waiver_accepted_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )

    # auto-filled by the set_booking_ref trigger — don't set this yourself
    booking_ref: Optional[str] = None

    created_at: Optional[datetime] = Field(default=None, sa_column=timestamp_column())
    updated_at: Optional[datetime] = Field(default=None, sa_column=timestamp_column())


# =========================================================
# rentals — 1 row per bike within a booking
# =========================================================
class Rental(SQLModel, table=True):
    __tablename__ = "rentals"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True),
    )
    booking_id: uuid.UUID = Field(foreign_key="bookings.id")
    bike_id: uuid.UUID = Field(foreign_key="bikes.id")

    # null until staff actually releases the bike (release_rental() sets both)
    released_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    due_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    returned_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )

    price: Decimal = Field(sa_column=Column(Numeric(10, 2), nullable=False))
    status: RentalStatus = Field(
        default=RentalStatus.reserved,
        sa_column=Column(EnumText(RentalStatus), nullable=False),
    )

    created_at: Optional[datetime] = Field(default=None, sa_column=timestamp_column())
    updated_at: Optional[datetime] = Field(default=None, sa_column=timestamp_column())


# =========================================================
# swap_requests
# =========================================================
class SwapRequest(SQLModel, table=True):
    __tablename__ = "swap_requests"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True),
    )
    rental_id: uuid.UUID = Field(foreign_key="rentals.id")
    reason: str
    status: SwapStatus = Field(
        default=SwapStatus.pending,
        sa_column=Column(EnumText(SwapStatus), nullable=False),
    )
    new_bike_id: Optional[uuid.UUID] = Field(default=None, foreign_key="bikes.id")
    handled_by_staff_id: Optional[uuid.UUID] = Field(
        default=None, foreign_key="users.id"
    )
    created_at: Optional[datetime] = Field(default=None, sa_column=timestamp_column())
    updated_at: Optional[datetime] = Field(default=None, sa_column=timestamp_column())


# =========================================================
# shop_settings — single row, id always = 1
# =========================================================
class ShopSettings(SQLModel, table=True):
    __tablename__ = "shop_settings"

    id: int = Field(default=1, primary_key=True)
    is_open: bool = Field(default=False)
    updated_at: Optional[datetime] = Field(
        default=None, sa_column=timestamp_column(nullable=True)
    )


# =========================================================
# shop_status_logs — auto-populated by sync_shop_status_log() trigger,
# never inserted into directly by FastAPI
# =========================================================
class ShopStatusLog(SQLModel, table=True):
    __tablename__ = "shop_status_logs"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True),
    )
    is_open: bool
    reason: Optional[str] = None
    changed_by_admin_id: Optional[uuid.UUID] = Field(
        default=None, foreign_key="users.id"
    )
    created_at: Optional[datetime] = Field(default=None, sa_column=timestamp_column())
    status: Optional[str] = None


# =========================================================
# audit_logs
# =========================================================
class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_logs"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True),
    )
    actor_id: Optional[uuid.UUID] = Field(default=None, foreign_key="users.id")
    action: str
    target_table: str
    target_id: Optional[uuid.UUID] = None
    details: Optional[dict] = Field(
        default=None, sa_column=Column(JSONB(none_as_null=True))
    )
    created_at: Optional[datetime] = Field(default=None, sa_column=timestamp_column())


# =========================================================
# API-facing request/response schemas
# (what routers actually accept/return — keeps request bodies
# from having to know about DB-only fields like balance_due)
# =========================================================
class BookingItemCreate(SQLModel):
    """One bike within a POST /bookings request."""
    bike_id: uuid.UUID


class BookingCreate(SQLModel):
    bikes: list[BookingItemCreate]
    expected_pickup_date: date
    rate_selected: RateSelected
    payment_method: PaymentMethod
    gcash_ref_no: Optional[str] = None
    gcash_receipt_url: Optional[str] = None
    waiver_version: str


class RentalRead(SQLModel):
    id: uuid.UUID
    bike_id: uuid.UUID
    # Denormalised so "My rides" can render a booking without also fetching the
    # whole catalogue to resolve every bike_id.
    bike_name: Optional[str] = None
    bike_type: Optional[BikeType] = None
    released_at: Optional[datetime]
    due_at: Optional[datetime]
    returned_at: Optional[datetime]
    price: Decimal
    status: RentalStatus


class BookingRead(SQLModel):
    id: uuid.UUID
    booking_ref: Optional[str]
    expected_pickup_date: date
    rate_selected: RateSelected
    total_price: Decimal = Field(schema_extra={"example": "250.00"})
    amount_paid: Decimal = Field(schema_extra={"example": "0.00"})
    balance_due: Decimal = Field(schema_extra={"example": "250.00"})
    payment_method: PaymentMethod
    payment_status: PaymentStatus
    booking_type: BookingType = BookingType.new
    created_at: Optional[datetime] = None
    rentals: list[RentalRead] = []

class BikeRead(SQLModel):
    id: uuid.UUID
    name: str
    type: BikeType
    status: BikeStatus
    daily_rate: Decimal
    weekly_rate: Optional[Decimal] = None
    image_url: Optional[str] = None
    # False only when the caller asked about a specific pickup date and the bike
    # is already reserved for it. Without a date there is nothing to check, so a
    # bike is "available" as long as it is in service.
    available: bool = True

class UserRead(SQLModel):
    id: uuid.UUID
    email: str
    name: str
    role: RoleName
    created_at: Optional[datetime] = None
    name_confirmed: bool
    tos_version_accepted: Optional[str] = None
    tos_accepted_at: Optional[datetime] = None
    is_active: bool


class StaffBookingRead(BookingRead):
    customer_name: str
    customer_email: str