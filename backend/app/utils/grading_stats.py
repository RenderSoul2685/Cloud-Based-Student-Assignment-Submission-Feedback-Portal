"""
Grading Statistics Calculation Utility.
Calculates statistical metrics (mean, max, min, graded/ungraded breakdown) for assignment deliverables.
"""
from typing import Any, Dict, List, Optional


def calculate_assignment_stats(
    assignment_id: str,
    max_marks: float,
    submissions: List[Dict[str, Any]],
    total_students_count: int,
) -> Dict[str, Any]:
    """
    Computes summary gradebook statistics for an assignment.
    
    Args:
        assignment_id: ID of the assignment.
        max_marks: Maximum attainable points for the assignment.
        submissions: List of submission documents for the assignment.
        total_students_count: Total count of enrolled/system students.
        
    Returns:
        Dict containing total_students, total_submissions, graded_count,
        ungraded_count, not_submitted_count, average_marks, highest_marks,
        lowest_marks, and max_marks.
    """
    graded_marks = [
        float(s["marks"])
        for s in submissions
        if (s.get("submission_status") == "GRADED" or s.get("marks") is not None)
        and s.get("marks") is not None
    ]

    total_submissions = len(submissions)
    graded_count = len(graded_marks)
    ungraded_count = total_submissions - graded_count
    not_submitted_count = max(0, total_students_count - total_submissions)

    if graded_marks:
        avg_marks = round(sum(graded_marks) / len(graded_marks), 2)
        high_marks = round(max(graded_marks), 2)
        low_marks = round(min(graded_marks), 2)
    else:
        avg_marks = None
        high_marks = None
        low_marks = None

    return {
        "assignment_id": assignment_id,
        "total_students": total_students_count,
        "total_submissions": total_submissions,
        "graded_count": graded_count,
        "ungraded_count": ungraded_count,
        "not_submitted_count": not_submitted_count,
        "average_marks": avg_marks,
        "highest_marks": high_marks,
        "lowest_marks": low_marks,
        "max_marks": float(max_marks),
    }
