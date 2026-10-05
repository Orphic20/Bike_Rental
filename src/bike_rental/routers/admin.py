"""Bike inventory management, shop open/closed toggle, users, audit log."""

import uuid
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func
from sqlmodel import Session, select

from bike_rental.auth import AdminUser
from bike_rental.database import SessionDep
from bike_rental.models import (
    AdminUserUpdate,
    AuditLog,
    AuditLogPageRead,
    AuditLogRead,
    Bike,
    BikeCreate,
    BikeRead,
    BikeStatus,
    BikeUpdate,
    Booking,
    PaymentMethod,
    PaymentMethodRevenueRead,
    PaymentStatus,
    RateRevenueRead,
    RateSelected,
    Rental,
    RentalStatus,
    RevenueReportRead,
    Role,
    RoleName,
    ShopSettings,
    ShopSettingsRead,
    ShopStatusLog,
    ShopUpdate,
    User,
    UserRead,
)
from bike_rental.routers.shop import to_shop_read

router = APIRouter(prefix="/admin", tags=["admin"])


def _to_bike_read(bike: Bike) -> BikeRead:
    return BikeRead(
        id=bike.id,
        name=bike.name,
        type=bike.type,
        status=bike.status,
        daily_rate=bike.daily_rate,
        weekly_rate=bike.weekly_rate,
        image_url=bike.image_url,
        available=(bike.status == BikeStatus.available),
    )


def _to_user_read(user: User, role: Role) -> UserRead:
    return UserRead(
        id=user.id,
        email=user.email,
        name=user.name,
        role=role.name,
        created_at=user.created_at,
        name_confirmed=user.name_confirmed,
        tos_version_accepted=user.tos_version_accepted,
        tos_accepted_at=user.tos_accepted_at,
        is_active=user.is_active,
    )


def _role_named(session: Session, name: RoleName) -> Role:
    role = session.exec(select(Role).where(Role.name == name)).first()
    if role is None:
        raise HTTPException(status_code=500, detail=f"Role {name.value} is missing")
    return role


def _other_active_admins(session: Session, user_id: uuid.UUID) -> list[uuid.UUID]:
    return session.exec(
        select(User.id)
        .join(Role, Role.id == User.role_id)
        .where(Role.name == RoleName.admin)
        .where(User.is_active.is_(True))
        .where(User.id != user_id)
    ).all()


@router.get("/reports/revenue", response_model=RevenueReportRead)
def get_revenue_report(
    user: AdminUser,
    session: SessionDep,
) -> RevenueReportRead:
    rows = session.exec(
        select(
            Booking.payment_method,
            Booking.rate_selected,
            func.sum(Booking.amount_paid),
        )
        .where(Booking.payment_status == PaymentStatus.paid)
        .group_by(Booking.payment_method, Booking.rate_selected)
    ).all()

    by_payment_method = PaymentMethodRevenueRead()
    by_rate = RateRevenueRead()
    total = Decimal("0.00")
    for payment_method, rate_selected, amount in rows:
        paid = amount or Decimal("0.00")
        total += paid
        if payment_method == PaymentMethod.cash:
            by_payment_method.cash += paid
        else:
            by_payment_method.gcash += paid
        if rate_selected == RateSelected.daily:
            by_rate.daily += paid
        else:
            by_rate.weekly += paid

    return RevenueReportRead(
        total=total,
        by_payment_method=by_payment_method,
        by_rate=by_rate,
    )


@router.get("/audit-logs", response_model=AuditLogPageRead)
def list_audit_logs(
    user: AdminUser,
    session: SessionDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> AuditLogPageRead:
    total = session.exec(select(func.count(AuditLog.id))).one()
    rows = session.exec(
        select(AuditLog, User)
        .join(User, User.id == AuditLog.actor_id, isouter=True)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return AuditLogPageRead(
        items=[
            AuditLogRead(
                id=log.id,
                actor_id=log.actor_id,
                actor_name=actor.name if actor else None,
                actor_email=actor.email if actor else None,
                action=log.action,
                target_table=log.target_table,
                target_id=log.target_id,
                details=log.details,
                created_at=log.created_at,
            )
            for log, actor in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/bikes", response_model=list[BikeRead])
def list_admin_bikes(
    user: AdminUser,
    session: SessionDep,
) -> list[BikeRead]:
    bikes = session.exec(select(Bike).order_by(Bike.name)).all()
    return [_to_bike_read(bike) for bike in bikes]


@router.post("/bikes", response_model=BikeRead)
def create_bike(
    user: AdminUser,
    session: SessionDep,
    body: BikeCreate,
) -> BikeRead:
    if body.status == BikeStatus.rented:
        raise HTTPException(status_code=400, detail="Cannot create a bike as rented")
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    taken = session.exec(
        select(Bike).where(func.lower(Bike.name) == name.lower())
    ).first()
    if taken:
        raise HTTPException(status_code=409, detail="A bike with this name already exists")
    bike = Bike(
        name=name,
        type=body.type,
        daily_rate=body.daily_rate,
        weekly_rate=body.weekly_rate,
        image_url=body.image_url,
        status=body.status,
    )
    session.add(bike)
    session.commit()
    session.refresh(bike)
    return _to_bike_read(bike)


@router.patch("/bikes/{bike_id}", response_model=BikeRead)
def update_bike(
    bike_id: uuid.UUID,
    body: BikeUpdate,
    user: AdminUser,
    session: SessionDep,
) -> BikeRead:
    bike = session.get(Bike, bike_id)
    if bike is None:
        raise HTTPException(status_code=404, detail="Bike not found")
    if body.status == BikeStatus.rented:
        raise HTTPException(status_code=400, detail="Cannot set a bike as rented")

    data = body.model_dump(exclude_unset=True)
    if "name" in data:
        name = (data["name"] or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="Name is required")
        taken = session.exec(
            select(Bike).where(
                func.lower(Bike.name) == name.lower(),
                Bike.id != bike.id,
            )
        ).first()
        if taken:
            raise HTTPException(
                status_code=409,
                detail="A bike with this name already exists",
            )
        data["name"] = name

    if "status" in data:
        outstanding = session.exec(
            select(Rental).where(
                Rental.bike_id == bike.id,
                Rental.status.in_((RentalStatus.active, RentalStatus.overdue)),
            )
        ).first()
        if outstanding:
            raise HTTPException(
                status_code=400,
                detail="Cannot change status while the bike is out",
            )

    for key, value in data.items():
        setattr(bike, key, value)
    session.add(bike)
    session.commit()
    session.refresh(bike)
    return _to_bike_read(bike)


@router.get("/users", response_model=list[UserRead])
def list_admin_users(
    user: AdminUser,
    session: SessionDep,
) -> list[UserRead]:
    rows = session.exec(
        select(User, Role)
        .join(Role, Role.id == User.role_id)
        .order_by(User.name, User.email)
    ).all()
    return [_to_user_read(row, role) for row, role in rows]


@router.patch("/users/{user_id}", response_model=UserRead)
def update_admin_user(
    user_id: uuid.UUID,
    body: AdminUserUpdate,
    user: AdminUser,
    session: SessionDep,
) -> UserRead:
    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="Nothing to update")

    target = session.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    current_role = session.get(Role, target.role_id)
    if current_role is None:
        raise HTTPException(status_code=500, detail="User has no role")

    new_role_name = data["role"] if "role" in data else current_role.name
    new_active = data["is_active"] if "is_active" in data else target.is_active

    if target.id == user.id:
        if new_role_name != RoleName.admin:
            raise HTTPException(
                status_code=400, detail="Cannot change your own role"
            )
        if not new_active:
            raise HTTPException(
                status_code=400, detail="Cannot suspend your own account"
            )

    was_active_admin = target.is_active and current_role.name == RoleName.admin
    will_be_active_admin = new_active and new_role_name == RoleName.admin
    if was_active_admin and not will_be_active_admin:
        if not _other_active_admins(session, target.id):
            raise HTTPException(
                status_code=400,
                detail="Cannot demote or suspend the last admin",
            )

    if "role" in data:
        target.role_id = _role_named(session, new_role_name).id
    if "is_active" in data:
        target.is_active = new_active

    session.add(target)
    session.commit()
    session.refresh(target)
    role = session.get(Role, target.role_id)
    if role is None:
        raise HTTPException(status_code=500, detail="User has no role")
    return _to_user_read(target, role)


@router.put("/shop/settings", response_model=ShopSettingsRead)
def update_shop_settings(
    body: ShopUpdate,
    user: AdminUser,
    session: SessionDep,
) -> ShopSettingsRead:
    settings = session.get(ShopSettings, 1)
    if settings is None:
        raise HTTPException(status_code=404, detail="Shop settings not found")
    settings.is_open = body.is_open
    session.add(settings)
    session.flush()

    reason = (body.reason or "").strip() or None
    log = session.exec(
        select(ShopStatusLog).order_by(ShopStatusLog.created_at.desc())
    ).first()
    if log:
        if not body.is_open and reason:
            log.reason = reason
        log.changed_by_admin_id = user.id
        session.add(log)

    session.commit()
    session.refresh(settings)
    return to_shop_read(session, settings)