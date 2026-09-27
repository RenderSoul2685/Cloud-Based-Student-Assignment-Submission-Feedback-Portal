# Cloud-Based Student Assignment Submission & Feedback Portal
## System Architecture & Design Document (Firebase Cloud Stack)

### 1. Project Overview
The **Cloud-Based Student Assignment Submission & Feedback Portal** is a cloud-native web application designed to streamline academic assignment distribution, student document submission, grading, and feedback delivery.

The application leverages a 100% free-tier, zero-cost cloud architecture on Google Cloud & Firebase (Spark Plan):
- **Frontend Layer**: Next.js (App Router, TypeScript, Tailwind CSS) + Firebase Client SDK (`firebase`)
- **Backend API Layer**: Python FastAPI + Firebase Admin SDK (`firebase-admin`)
- **Cloud Database (NoSQL Document Store)**: Google Cloud Firestore (Native Mode)
- **Cloud Object Storage (Unstructured Documents)**: Firebase Storage (Google Cloud Storage Bucket)
- **Authentication & Identity**: Firebase Authentication (Email/Password & JWT ID Token verification)

---

### 2. High-Level Architecture Diagram (ASCII)

```text
+-----------------------------------------------------------------------------------+
|                                  USER LAYER                                       |
|  +-------------------------------------+  +------------------------------------+  |
|  |           Student Client            |  |          Instructor Client         |  |
|  | (Upload Assignment, View Feedback)  |  |   (Create Tasks, Grade, Feedback)  |  |
|  +-------------------------------------+  +------------------------------------+  |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v  [HTTPS / Web SDK / REST]
+-----------------------------------------------------------------------------------+
|                             PRESENTATION LAYER (Next.js)                          |
|  - Modern Web UI (SSR & Client Components with Tailwind CSS)                      |
|  - Firebase Client SDK (Auth State, Direct Storage Uploads / Token Passing)       |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v  [Bearer ID Token / REST API]
+-----------------------------------------------------------------------------------+
|                     APPLICATION LAYER (FastAPI Backend + Admin SDK)               |
|                                                                                   |
|  +------------------+  +-------------------+  +--------------------------------+  |
|  | Firebase Auth    |  | Validation & DTOs |  | Cloud Service Layer            |  |
|  | Token Middleware |  | (Pydantic Models) |  | (Firestore / Storage / Auth)   |  |
|  +------------------+  +-------------------+  +--------------------------------+  |
|                                     |                                             |
|        +----------------------------+----------------------------+                |
|        |                                                         |                |
|        v [Document Reads / Writes]                               v [Signed URLs]  |
+--------+---------------------------------------------------------+----------------+
         |                                                         |
         v                                                         v
+-----------------------------------+     +-----------------------------------------+
|      DATABASE LAYER (Firestore)   |     |    OBJECT STORAGE (Firebase Storage)    |
|   Google Cloud Firestore (NoSQL)  |     |   Google Cloud Storage (GCS Bucket)     |
|-----------------------------------|     |-----------------------------------------|
|  - /users/{uid}                   |     |  - submissions/{courseId}/              |
|  - /courses/{courseId}            |     |    {assignmentId}/{studentId}/{file}    |
|  - .../assignments/{assignmentId} |     |  - Student PDFs, code ZIPs, reports     |
|  - /submissions/{submissionId}    |     |  - Instructor attachments & rubrics     |
+-----------------------------------+     +-----------------------------------------+
```

---

### 3. Detailed End-to-End Request Flow

#### A. Authentication & Authorization Flow
1. User authenticates via the Next.js frontend using **Firebase Authentication**.
2. Firebase Auth issues a cryptographically signed JWT **ID Token** containing the user's `uid`, email, and custom claims (e.g., `role: "STUDENT"` or `role: "TEACHER"`).
3. The frontend passes this token in the `Authorization: Bearer <ID_TOKEN>` header for backend requests.
4. FastAPI's Auth Service verifies the token via `firebase_admin.auth.verify_id_token()`.

#### B. Assignment Creation & Submission Flow
1. **Assignment Creation**: Teacher posts an assignment to `/courses/{courseId}/assignments/{assignmentId}` in Firestore.
2. **File Upload**: Student uploads assignment document (PDF/ZIP) to Firebase Storage under path `submissions/{courseId}/{assignmentId}/{studentId}/{fileName}`.
3. **Submission Metadata Record**: A submission document is created in the top-level `/submissions/{submissionId}` collection referencing `assignment_id`, `course_id`, `student_id`, and `storage_path`.
4. **Status Evaluation**: Status is automatically set to `SUBMITTED` or `LATE` depending on whether submission time precedes assignment `deadline`.

#### C. Grading & Feedback Flow
1. **Submissions Listing**: Instructor queries `/submissions` filtering by `course_id` or `assignment_id`.
2. **Secure Document Review**: The backend generates a time-limited signed URL or uses Firebase Storage secure token for instructor document inspection.
3. **Grade & Feedback Update**: Instructor updates the submission record with `marks`, `feedback`, and `graded_at`, transitioning status to `GRADED`.

---

### 4. Why Denormalized NoSQL (Firestore) vs Relational Design (RDS)?

This project shifted from a traditional relational database (PostgreSQL/RDS) to Google Cloud Firestore for clear operational, cost, and architectural benefits:

| Architectural Factor | Cloud Firestore (NoSQL) | Relational Database (RDS PostgreSQL) |
| :--- | :--- | :--- |
| **Cost & Free Tier** | **100% Free on Spark Plan** (1GB storage, 50k reads/day, 20k writes/day, no credit card required) | Expensive ($15–$30+/mo after free tier or if misconfigured) |
| **Operational Overhead** | Serverless: zero database server management, patching, or connection pooling | Requires VM provisioning, subnet routing, connection limits |
| **Schema Flexibility** | Document JSON model accommodates dynamic fields, nested rubrics, and feedback metadata | Rigid DDL migrations required for any schema alteration |
| **Realtime Sync** | Native document snapshot listeners for live grade/submission updates | Requires complex WebSocket or polling setups |
| **Offline Emulator** | Firebase Local Emulator Suite provides full offline testing with zero cloud dependency | Requires Docker containers or local Postgres installation |

---

### 5. Firestore Collection Structure & Query/Index Design

#### A. Hierarchy Structure
1. **`/users/{uid}`**:
   - Stores user profiles keyed directly by their Firebase Auth UID (`name`, `email`, `role`, `created_at`).
2. **`/courses/{courseId}`**:
   - Course documents representing classes (`course_name`, `teacher_id`, `created_at`).
3. **`/courses/{courseId}/assignments/{assignmentId}` (Subcollection)**:
   - Nested subcollection under the course document. This structure ensures **hierarchical encapsulation**: an assignment naturally belongs to exactly one course, and course deletion cleans up assignments.
4. **`/submissions/{submissionId}` (Top-Level Collection)**:
   - Kept as a **top-level collection** (rather than a deep subcollection under assignments) because submissions need to be queried across multiple dimensions:
     - **By Student**: `submissions.where("student_id", "==", uid)` (Student dashboard).
     - **By Assignment**: `submissions.where("assignment_id", "==", aid)` (Teacher grading table).
     - **By Course & Status**: `submissions.where("course_id", "==", cid).where("submission_status", "==", "SUBMITTED")` (Pending review queue).

#### B. Indexing Strategy
- **Single-Field Indexes**: Firestore automatically creates single-field ascending and descending indexes for all basic fields.
- **Composite Indexes**: For multi-condition queries (e.g., querying submissions by `course_id` ordered by `submitted_at`), Firestore composite indexes are defined in `firestore.indexes.json`:
  - `course_id` (ASC) + `submitted_at` (DESC)
  - `assignment_id` (ASC) + `submission_status` (ASC)
  - `student_id` (ASC) + `submitted_at` (DESC)
- **Collection Group Queries**: If searching assignments globally across all courses, Firestore's collection group index on `assignments` enables `db.collection_group("assignments")`.

---

### 6. Separation of Metadata (Firestore) from Files (Firebase Storage)

Storing large binaries (PDFs, ZIP files) directly in Firestore documents is prohibited by Firestore's 1MB document limit. Separating **Firestore (Document Metadata)** from **Firebase Storage (Unstructured Blobs)** ensures:
1. **High Query Performance**: Firestore document fetches remain small (few kilobytes), preserving read quotas.
2. **Massive Storage Capacity**: Firebase Storage supports files up to 5TB per upload with global CDN delivery.
3. **Secure Direct Uploads**: Clients can upload directly to Storage via Firebase SDK or secure signed URLs without burdening the FastAPI backend memory or CPU.
