"""
File Validation Utilities for Assignment Submissions.
Enforces file extension and maximum file size policies.
"""
from typing import List, Optional, Tuple

DEFAULT_ALLOWED_EXTENSIONS = ["pdf", "docx", "png", "jpg", "jpeg"]
DEFAULT_MAX_SIZE_MB = 20.0
BYTES_PER_MB = 1024 * 1024


def validate_file_extension(
    filename: str,
    allowed_types: Optional[List[str]] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Validates whether the file's extension is in the allowed list.
    
    Args:
        filename: Name of the uploaded file (e.g., "report.pdf")
        allowed_types: List of allowed extensions (defaults to ['pdf', 'docx', 'png', 'jpg', 'jpeg'])
        
    Returns:
        (is_valid, error_message): Tuple indicating validation status and error string if invalid.
    """
    if not filename or "." not in filename:
        return False, "File must have a valid extension."

    ext = filename.rsplit(".", 1)[1].lower().strip()
    allowed = [t.lower().lstrip(".").strip() for t in (allowed_types or DEFAULT_ALLOWED_EXTENSIONS)]

    if ext not in allowed:
        return False, f"File type '.{ext}' is not permitted. Allowed extensions: {', '.join(allowed)}."

    return True, None


def validate_file_size(
    size_bytes: int,
    max_size_mb: float = DEFAULT_MAX_SIZE_MB,
) -> Tuple[bool, Optional[str]]:
    """
    Validates whether the file size is within the allowed threshold.
    
    Args:
        size_bytes: Size of the file in bytes.
        max_size_mb: Maximum allowed size in megabytes (defaults to 20MB).
        
    Returns:
        (is_valid, error_message): Tuple indicating validation status and error string if invalid.
    """
    max_bytes = int(max_size_mb * BYTES_PER_MB)

    if size_bytes <= 0:
        return False, "Uploaded file is empty (0 bytes)."

    if size_bytes > max_bytes:
        size_mb = round(size_bytes / BYTES_PER_MB, 2)
        return (
            False,
            f"File size ({size_mb} MB) exceeds maximum allowed limit of {max_size_mb} MB.",
        )

    return True, None
