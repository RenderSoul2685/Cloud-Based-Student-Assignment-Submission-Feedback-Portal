# Cloud-Based Student Assignment Submission & Feedback Portal

A cloud-native assignment management and grading portal built for Cloud Computing coursework, running 100% on **Google Cloud & Firebase Spark Free Tier** (Zero Cost).

## 🚀 Tech Stack
- **Frontend**: Next.js (App Router, TypeScript, Tailwind CSS) + Firebase Client SDK
- **Backend**: Python FastAPI + Firebase Admin SDK (`firebase-admin`)
- **Database**: Google Cloud Firestore (NoSQL Document Store, Free Spark Plan)
- **Object Storage**: Firebase Storage (Google Cloud Storage Bucket, Free Spark Plan)
- **Authentication**: Firebase Authentication (Email/Password & JWT ID Token Verification)
- **Legacy Architecture**: Archived in `legacy_rds/` (AWS RDS / PostgreSQL / SQLAlchemy implementation for reference).

---

## 📁 Repository Structure

```text
Cloud-Assignment-Submission-Portal/
├── frontend/                     # Next.js App Router Frontend + Firebase SDK
│   ├── app/                      # Next.js pages, layouts, and components
│   ├── package.json              # Frontend npm dependencies (includes firebase)
│   └── tsconfig.json             # TypeScript configuration
├── backend/                      # Python FastAPI Backend
│   ├── app/                      # Application modular structure
│   │   ├── routes/               # API route handlers
│   │   ├── models/               # Firestore schemas & Pydantic models
│   │   ├── services/             # Core business logic
│   │   ├── middleware/           # Auth & logging middleware
│   │   ├── utils/                # Helper utilities
│   │   ├── firebase_config.py    # Firebase Admin SDK initialization
│   │   ├── db_init.py            # Firestore collections seed script
│   │   └── main.py               # FastAPI entry point & health check
│   └── requirements.txt          # Python backend dependencies
├── cloud/                        # Cloud service abstraction adapters
│   ├── database_service.py       # Firestore database wrapper
│   ├── storage_service.py        # Firebase Storage wrapper
│   └── auth_service.py           # Firebase Auth verification wrapper
├── legacy_rds/                   # Archived AWS RDS / SQLAlchemy code
├── tests/                        # Automated unit & integration tests
│   ├── test_firestore.py         # Firestore collections & seed validation
│   └── test_health.py            # API health check test
├── docs/                         # System architecture & setup documentation
│   ├── architecture.md           # NoSQL architecture & index design
│   └── firebase_setup.md         # Firebase console setup guide (Spark plan)
├── sample_files/                 # Sample assignment submissions for testing
├── screenshots/                  # Architecture & UI screenshots
├── reports/                      # Evaluation & project reports
├── README.md                     # Project overview and setup guide
├── .env.example                  # Environment configuration template
└── .gitignore                    # Monorepo gitignore
```

---

## 🛠️ Quick Start

### 1. Backend Setup (FastAPI)
```bash
# Navigate to backend directory
cd backend

# Install dependencies
pip install -r requirements.txt

# Seed Firestore database with dummy data
python -m backend.app.db_init

# Start backend server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
- Health Check Endpoint: `http://localhost:8000/api/health`
- Interactive Swagger Docs: `http://localhost:8000/docs`

### 2. Frontend Setup (Next.js)
```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```
Frontend URL: `http://localhost:3000`

---

## 📖 Setup & Architecture Documentation
- **Firebase Setup Guide (Spark Plan Zero Cost Guarantee)**: [docs/firebase_setup.md](docs/firebase_setup.md)
- **Architecture & NoSQL Design**: [docs/architecture.md](docs/architecture.md)
