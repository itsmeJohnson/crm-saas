import uuid
from datetime import datetime, date, time
from sqlalchemy import String, ForeignKey, Boolean, Integer, Date, Time, DateTime, Numeric, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class Shift(BaseModel):
    """A named work shift: start/end wall-clock times (interpreted in the org
    timezone), an unpaid break allowance, a grace window for late arrivals, and
    the set of working weekdays. Night shifts (end < start) are supported."""
    __tablename__ = "shifts"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_shift_org_code"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    break_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # allotted unpaid break
    grace_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # late-login grace window
    working_days: Mapped[list | None] = mapped_column(JSON, nullable=True)  # ["mon","tue",...]; null = Mon-Fri
    is_night_shift: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False, index=True)  # active|archived
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


class ShiftAssignment(BaseModel):
    """Assigns a user to a shift over a date range (end_date null = ongoing).
    The active shift for a user on a date is the assignment with the latest
    start_date whose range covers that date."""
    __tablename__ = "shift_assignments"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    shift_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shifts.id", ondelete="CASCADE"), nullable=False, index=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)


class AttendanceRecord(BaseModel):
    """One row per user per work date. Captures clock-in/out, computed late/early
    flags and worked/break minutes, optional geo coordinates, and the capture
    source (web | biometric | mobile) so device sync can write records too."""
    __tablename__ = "attendance_records"
    __table_args__ = (UniqueConstraint("organization_id", "user_id", "work_date", name="uq_attendance_user_date"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    shift_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("shifts.id"), nullable=True, index=True)
    clock_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    clock_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # present|absent|late|half_day|on_leave|holiday|weekly_off
    status: Mapped[str] = mapped_column(String(20), default="present", nullable=False, index=True)
    is_late: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    late_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_early_logout: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    early_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    worked_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    break_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Geo (optional)
    in_latitude: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    in_longitude: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    out_latitude: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    out_longitude: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="web", nullable=False)  # web|biometric|mobile
    device_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class AttendanceBreak(BaseModel):
    """A single break session within an attendance record. Open while break_end
    is null; on resume, minutes are computed and folded into the record."""
    __tablename__ = "attendance_breaks"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    attendance_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("attendance_records.id", ondelete="CASCADE"), nullable=False, index=True)
    break_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    break_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)


class AttendanceCorrection(BaseModel):
    """A request to fix an attendance record (or add a missing day). Proposed
    values live in `proposed` JSON; a Manager/OrgAdmin approves or rejects, and
    approval applies the changes to the record."""
    __tablename__ = "attendance_corrections"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    attendance_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("attendance_records.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    proposed: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {clock_in_at, clock_out_at, status}
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)  # pending|approved|rejected
    requested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
