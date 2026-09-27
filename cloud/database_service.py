"""
Cloud Firestore Database Service Adapter.
Provides document-based CRUD and query operations for Firestore.
Spark Plan Zero-Cost Architecture.
"""
from typing import Any, Dict, List, Optional
from google.cloud.firestore import Client as FirestoreClient
from backend.app.firebase_config import get_firestore_client


class DatabaseService:
    """
    Firestore Database Service wrapper.
    Decouples raw SDK calls from high-level backend business logic.
    """

    def __init__(self, client: Optional[FirestoreClient] = None):
        self._client = client

    @property
    def client(self) -> FirestoreClient:
        if self._client is None:
            self._client = get_firestore_client()
        return self._client

    # ==============================================================================
    # User Collection Operations (/users/{uid})
    # ==============================================================================
    def create_user(self, uid: str, data: Dict[str, Any]) -> Dict[str, Any]:
        doc_ref = self.client.collection("users").document(uid)
        doc_ref.set(data)
        return {"uid": uid, **data}

    def get_user(self, uid: str) -> Optional[Dict[str, Any]]:
        doc = self.client.collection("users").document(uid).get()
        if doc.exists:
            return {"uid": doc.id, **doc.to_dict()}
        return None

    def list_users(self, role: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            if role:
                query = self.client.collection("users").where("role", "==", role)
                docs = query.stream()
            else:
                docs = self.client.collection("users").stream()
            return [{"uid": doc.id, **doc.to_dict()} for doc in docs]
        except Exception:
            # Fallback for mock stores
            docs = self.client.collection("users").stream()
            results = []
            for doc in docs:
                data = doc.to_dict()
                u_role = data.get("role")
                if hasattr(u_role, "value"):
                    u_role = u_role.value
                if not role or u_role == role:
                    results.append({"uid": doc.id, **data})
            return results

    def list_students(self) -> List[Dict[str, Any]]:
        return self.list_users(role="STUDENT")

    # ==============================================================================
    # Course Collection Operations (/courses/{courseId})
    # ==============================================================================
    def create_course(self, course_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        doc_ref = self.client.collection("courses").document(course_id)
        doc_ref.set(data)
        return {"course_id": course_id, **data}

    def get_course(self, course_id: str) -> Optional[Dict[str, Any]]:
        doc = self.client.collection("courses").document(course_id).get()
        if doc.exists:
            return {"course_id": doc.id, **doc.to_dict()}
        return None

    def list_courses(self) -> List[Dict[str, Any]]:
        docs = self.client.collection("courses").stream()
        return [{"course_id": doc.id, **doc.to_dict()} for doc in docs]

    def list_courses_by_teacher(self, teacher_id: str) -> List[Dict[str, Any]]:
        # Supports query on teacher_id
        try:
            query = self.client.collection("courses").where("teacher_id", "==", teacher_id)
            docs = query.stream()
            return [{"course_id": doc.id, **doc.to_dict()} for doc in docs]
        except Exception:
            # Fallback for mock in-memory stores that don't implement .where()
            all_courses = self.list_courses()
            return [c for c in all_courses if c.get("teacher_id") == teacher_id]

    def update_course(self, course_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        doc_ref = self.client.collection("courses").document(course_id)
        if hasattr(doc_ref, "update"):
            doc_ref.update(data)
        else:
            current = self.get_course(course_id) or {}
            current.update(data)
            doc_ref.set(current)
        return self.get_course(course_id)

    def delete_course(self, course_id: str) -> bool:
        doc_ref = self.client.collection("courses").document(course_id)
        doc = doc_ref.get()
        if doc.exists:
            doc_ref.delete()
            return True
        return False

    # ==============================================================================
    # Assignment Subcollection Operations (/courses/{courseId}/assignments/{assignmentId})
    # ==============================================================================
    def create_assignment(
        self,
        course_id: str,
        assignment_id: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        doc_ref = (
            self.client.collection("courses")
            .document(course_id)
            .collection("assignments")
            .document(assignment_id)
        )
        doc_ref.set(data)
        return {"assignment_id": assignment_id, "course_id": course_id, **data}

    def get_assignment(self, course_id: str, assignment_id: str) -> Optional[Dict[str, Any]]:
        doc = (
            self.client.collection("courses")
            .document(course_id)
            .collection("assignments")
            .document(assignment_id)
            .get()
        )
        if doc.exists:
            return {"assignment_id": doc.id, "course_id": course_id, **doc.to_dict()}
        return None

    def find_assignment_by_id(self, assignment_id: str) -> Optional[Dict[str, Any]]:
        """
        Locates an assignment across courses by assignment_id.
        Tries collection_group query, falling back to course traversal.
        """
        try:
            docs = self.client.collection_group("assignments").where("assignment_id", "==", assignment_id).stream()
            for doc in docs:
                data = doc.to_dict()
                course_id = data.get("course_id") or doc.reference.parent.parent.id
                return {"assignment_id": doc.id, "course_id": course_id, **data}
        except Exception:
            pass

        # Traversal fallback (works on real Firestore & mock stores)
        courses = self.list_courses()
        for c in courses:
            c_id = c.get("course_id")
            if not c_id:
                continue
            assign = self.get_assignment(c_id, assignment_id)
            if assign:
                return assign
        return None

    def list_assignments(
        self,
        course_id: str,
        include_deleted: bool = False,
    ) -> List[Dict[str, Any]]:
        course_ref = self.client.collection("courses").document(course_id)
        docs = course_ref.collection("assignments").stream()
        results = []
        for doc in docs:
            item = {"assignment_id": doc.id, "course_id": course_id, **doc.to_dict()}
            if not include_deleted and item.get("is_deleted") is True:
                continue
            results.append(item)
        return results

    def update_assignment(
        self,
        course_id: str,
        assignment_id: str,
        data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        doc_ref = (
            self.client.collection("courses")
            .document(course_id)
            .collection("assignments")
            .document(assignment_id)
        )
        if hasattr(doc_ref, "update"):
            doc_ref.update(data)
        else:
            current = self.get_assignment(course_id, assignment_id) or {}
            current.update(data)
            doc_ref.set(current)
        return self.get_assignment(course_id, assignment_id)

    def delete_assignment(self, course_id: str, assignment_id: str) -> bool:
        doc_ref = (
            self.client.collection("courses")
            .document(course_id)
            .collection("assignments")
            .document(assignment_id)
        )
        doc = doc_ref.get()
        if doc.exists:
            doc_ref.delete()
            return True
        return False

    # ==============================================================================
    # Submission Collection Operations (/submissions/{submissionId})
    # ==============================================================================
    def create_submission(self, submission_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        doc_ref = self.client.collection("submissions").document(submission_id)
        doc_ref.set(data)
        return {"submission_id": submission_id, **data}

    def get_submission(self, submission_id: str) -> Optional[Dict[str, Any]]:
        doc = self.client.collection("submissions").document(submission_id).get()
        if doc.exists:
            return {"submission_id": doc.id, **doc.to_dict()}
        return None

    def get_submission_by_student_and_assignment(
        self,
        assignment_id: str,
        student_id: str,
    ) -> Optional[Dict[str, Any]]:
        try:
            query = (
                self.client.collection("submissions")
                .where("assignment_id", "==", assignment_id)
                .where("student_id", "==", student_id)
            )
            docs = list(query.stream())
            if docs:
                return {"submission_id": docs[0].id, **docs[0].to_dict()}
        except Exception:
            pass

        # Fallback for mock stores
        try:
            docs = self.client.collection("submissions").stream()
            for doc in docs:
                data = doc.to_dict()
                if data.get("assignment_id") == assignment_id and data.get("student_id") == student_id:
                    return {"submission_id": doc.id, **data}
        except Exception:
            pass
        return None

    def list_submissions_by_student(self, student_id: str) -> List[Dict[str, Any]]:
        try:
            query = self.client.collection("submissions").where("student_id", "==", student_id)
            docs = query.stream()
            return [{"submission_id": doc.id, **doc.to_dict()} for doc in docs]
        except Exception:
            try:
                docs = self.client.collection("submissions").stream()
                return [
                    {"submission_id": doc.id, **doc.to_dict()}
                    for doc in docs
                    if doc.to_dict().get("student_id") == student_id
                ]
            except Exception:
                return []

    def list_submissions_by_assignment(self, assignment_id: str) -> List[Dict[str, Any]]:
        try:
            query = self.client.collection("submissions").where("assignment_id", "==", assignment_id)
            docs = query.stream()
            return [{"submission_id": doc.id, **doc.to_dict()} for doc in docs]
        except Exception:
            try:
                docs = self.client.collection("submissions").stream()
                return [
                    {"submission_id": doc.id, **doc.to_dict()}
                    for doc in docs
                    if doc.to_dict().get("assignment_id") == assignment_id
                ]
            except Exception:
                return []

    def update_submission(self, submission_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        doc_ref = self.client.collection("submissions").document(submission_id)
        if hasattr(doc_ref, "update"):
            doc_ref.update(data)
        else:
            current = self.get_submission(submission_id) or {}
            current.update(data)
            doc_ref.set(current)
        return self.get_submission(submission_id)

    def has_submissions_for_assignment(self, course_id: str, assignment_id: str) -> bool:
        """
        Checks if any submission exists for the given assignment.
        Used to determine whether to soft-delete or hard-delete an assignment.
        """
        try:
            docs = self.client.collection("submissions").where("assignment_id", "==", assignment_id).stream()
            for _ in docs:
                return True
            return False
        except Exception:
            # Fallback for mock stores
            docs = self.client.collection("submissions").stream()
            for doc in docs:
                data = doc.to_dict()
                if data.get("assignment_id") == assignment_id:
                    return True
            return False
