"""Pydantic models for Train Monitor."""

from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field


class MonitoringMode(str, Enum):
    """Station monitoring mode."""
    DEPARTURES = "departures"  # Only departures
    ARRIVALS = "arrivals"      # Only arrivals
    BOTH = "both"              # Both departures and arrivals


class ServiceStatus(str, Enum):
    """Train service status."""
    ON_TIME = "on_time"
    DELAYED = "delayed"
    CANCELLED = "cancelled"
    NO_REPORT = "no_report"


class ChangeType(str, Enum):
    """Type of schedule change."""
    DELAY = "delay"
    CANCELLATION = "cancellation"
    PLATFORM_CHANGE = "platform_change"
    TIME_CHANGE = "time_change"
    NEW_SERVICE = "new_service"
    STATUS_CHANGE = "status_change"


class ChangeSeverity(str, Enum):
    """Severity of the change."""
    LOW = "low"        # Small delay (< 5 minutes)
    MEDIUM = "medium"  # Medium delay (5-15 minutes) or platform change
    HIGH = "high"      # Large delay (> 15 minutes) or cancellation


class NotificationFilter(BaseModel):
    """Filters for notifications."""

    min_delay_minutes: int = Field(
        default=5,
        description="Minimum delay for notification (minutes)"
    )
    notify_cancellations: bool = Field(
        default=True,
        description="Notify about cancellations"
    )
    notify_platform_changes: bool = Field(
        default=True,
        description="Notify about platform changes"
    )
    notify_new_services: bool = Field(
        default=False,
        description="Notify about new services"
    )
    destination_filter: Optional[List[str]] = Field(
        default=None,
        description="Filter by destination CRS codes (None = all destinations)"
    )
    time_range_start: Optional[str] = Field(
        default=None,
        description="Time window start (HH:MM), None = no restriction"
    )
    time_range_end: Optional[str] = Field(
        default=None,
        description="Time window end (HH:MM), None = no restriction"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "min_delay_minutes": 5,
                "notify_cancellations": True,
                "notify_platform_changes": True,
                "notify_new_services": False,
                "destination_filter": ["CBG", "KGX"],
                "time_range_start": "06:00",
                "time_range_end": "22:00"
            }
        }


class StationConfig(BaseModel):
    """Station monitoring configuration."""

    # Core parameters
    crs_code: str = Field(
        ...,
        min_length=3,
        max_length=3,
        description="3-letter CRS station code (e.g., ELY)"
    )
    station_name: str = Field(
        ...,
        description="Station name (for logs and notifications)"
    )
    enabled: bool = Field(
        default=True,
        description="Whether monitoring is enabled"
    )

    # Monitoring parameters
    monitoring_mode: MonitoringMode = Field(
        default=MonitoringMode.DEPARTURES,
        description="Monitoring mode"
    )
    check_interval_minutes: int = Field(
        default=5,
        ge=1,
        le=60,
        description="Check interval (1-60 minutes)"
    )
    time_window_minutes: int = Field(
        default=120,
        ge=30,
        le=240,
        description="Time window for API requests (30-240 minutes)"
    )
    max_services: int = Field(
        default=50,
        ge=1,
        le=150,
        description="Maximum number of services to fetch (1-150)"
    )

    # Telegram notifications
    telegram_chat_ids: List[str] = Field(
        default_factory=list,
        description="List of Telegram chat IDs for notifications (empty = no notifications)"
    )
    notification_enabled: bool = Field(
        default=True,
        description="Whether notifications are enabled"
    )

    # Filters
    filters: NotificationFilter = Field(
        default_factory=NotificationFilter,
        description="Notification filters"
    )

    # Metadata
    description: Optional[str] = Field(
        default=None,
        description="Description/note"
    )
    added_at: Optional[datetime] = Field(
        default=None,
        description="Date added"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Tags for grouping"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "crs_code": "ELY",
                "station_name": "Ely",
                "enabled": True,
                "monitoring_mode": "departures",
                "check_interval_minutes": 5,
                "time_window_minutes": 120,
                "telegram_chat_ids": ["-1001234567890", "-1009876543210"],
                "notification_enabled": True,
                "filters": {
                    "min_delay_minutes": 5,
                    "notify_cancellations": True,
                    "notify_platform_changes": True,
                    "destination_filter": ["CBG", "KGX"]
                },
                "description": "Main daily commute station",
                "tags": ["daily", "priority"]
            }
        }


class TrainService(BaseModel):
    """Train service model."""

    service_id: str = Field(..., description="Unique service ID")
    origin: str = Field(..., description="Origin station")
    destination: str = Field(..., description="Destination station")
    destination_crs: Optional[str] = Field(None, description="Destination CRS code")

    scheduled_departure: Optional[str] = Field(None, description="Scheduled departure time")
    estimated_departure: Optional[str] = Field(None, description="Estimated departure time")
    actual_departure: Optional[str] = Field(None, description="Actual departure time")

    scheduled_arrival: Optional[str] = Field(None, description="Scheduled arrival time")
    estimated_arrival: Optional[str] = Field(None, description="Estimated arrival time")
    actual_arrival: Optional[str] = Field(None, description="Actual arrival time")

    platform: Optional[str] = Field(None, description="Platform number")
    status: ServiceStatus = Field(default=ServiceStatus.NO_REPORT, description="Service status")
    delay_minutes: int = Field(default=0, description="Delay in minutes")
    operator: Optional[str] = Field(None, description="Train operator")
    is_cancelled: bool = Field(default=False, description="Whether service is cancelled")
    cancellation_reason: Optional[str] = Field(None, description="Cancellation reason")

    class Config:
        json_schema_extra = {
            "example": {
                "service_id": "ABC123",
                "origin": "Ely",
                "destination": "Cambridge",
                "destination_crs": "CBG",
                "scheduled_departure": "14:30",
                "estimated_departure": "14:45",
                "platform": "2",
                "status": "delayed",
                "delay_minutes": 15,
                "operator": "Greater Anglia",
                "is_cancelled": False
            }
        }


class TrainChange(BaseModel):
    """Train schedule change."""

    change_type: ChangeType = Field(..., description="Type of change")
    service_id: str = Field(..., description="Service ID")
    service: TrainService = Field(..., description="Service data")

    old_value: Optional[str] = Field(None, description="Old value")
    new_value: str = Field(..., description="New value")

    severity: ChangeSeverity = Field(..., description="Severity of change")
    timestamp: datetime = Field(default_factory=datetime.now, description="Detection time")

    message: Optional[str] = Field(None, description="Change message")

    class Config:
        json_schema_extra = {
            "example": {
                "change_type": "delay",
                "service_id": "ABC123",
                "old_value": "14:30",
                "new_value": "14:45",
                "severity": "medium",
                "message": "Delayed by 15 minutes"
            }
        }


class StationBoard(BaseModel):
    """Station departure/arrival board."""

    station_crs: str = Field(..., description="Station CRS code")
    station_name: str = Field(..., description="Station name")
    generated_at: datetime = Field(default_factory=datetime.now, description="Generation time")
    services: List[TrainService] = Field(default_factory=list, description="List of services")

    class Config:
        json_schema_extra = {
            "example": {
                "station_crs": "ELY",
                "station_name": "Ely",
                "generated_at": "2025-12-28T14:30:00",
                "services": []
            }
        }
