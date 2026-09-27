"""
Deadline and Timestamp Utility Functions.
Provides timezone-safe comparison for assignment submissions.
"""
from datetime import datetime, timezone
from typing import Union


def ensure_utc(dt: datetime) -> datetime:
    """
    Ensures datetime is timezone-aware and converted to UTC.
    If naive, assumes UTC.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def is_late(submitted_at: datetime, deadline: datetime) -> bool:
    """
    Determines whether a submission is late compared to the assignment deadline.
    
    Rules:
    - Submission at or before the deadline is ON-TIME (returns False).
    - Submission strictly after the deadline is LATE (returns True).
    - Safely converts both timestamps to UTC before comparison to prevent timezone skew.
    
    Args:
        submitted_at: Timestamp when submission was received on the server.
        deadline: Configured assignment deadline.
        
    Returns:
        bool: True if strictly after deadline, False if on-time.
    """
    sub_utc = ensure_utc(submitted_at)
    dl_utc = ensure_utc(deadline)
    return sub_utc > dl_utc
