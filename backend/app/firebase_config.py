"""
Firebase Admin SDK Initialization and Client Providers.
Supports Service Account JSON credentials, Firebase Emulators, and mock fallback.
"""
import os
import logging
from typing import Optional
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore, auth, storage
from google.cloud.firestore import Client as FirestoreClient

load_dotenv()
logger = logging.getLogger("firebase_config")

# Environment variables
SERVICE_ACCOUNT_PATH = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "assignment-portal-demo")
STORAGE_BUCKET = os.getenv("FIREBASE_STORAGE_BUCKET", f"{PROJECT_ID}.firebasestorage.app")
FIRESTORE_EMULATOR_HOST = os.getenv("FIRESTORE_EMULATOR_HOST")


def get_firebase_app():
    """Initializes or retrieves the singleton Firebase Admin app."""
    if firebase_admin._apps:
        return firebase_admin.get_app()

    # 1. If service account JSON file exists on disk
    if SERVICE_ACCOUNT_PATH and os.path.exists(SERVICE_ACCOUNT_PATH):
        logger.info(f"Initializing Firebase Admin with Service Account at: {SERVICE_ACCOUNT_PATH}")
        cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
        return firebase_admin.initialize_app(
            cred,
            {
                "projectId": PROJECT_ID,
                "storageBucket": STORAGE_BUCKET,
            },
        )

    # 2. If running against Firestore Emulator
    if FIRESTORE_EMULATOR_HOST:
        logger.info(f"Initializing Firebase Admin in Emulator Mode at: {FIRESTORE_EMULATOR_HOST}")
        # In emulator mode or GCP environment without service account file
        os.environ.setdefault("FIRESTORE_EMULATOR_HOST", FIRESTORE_EMULATOR_HOST)
        return firebase_admin.initialize_app(
            options={
                "projectId": PROJECT_ID,
                "storageBucket": STORAGE_BUCKET,
            }
        )

    # 3. Default fallback / testing mode (uses default or demo project)
    logger.info("Initializing Firebase Admin with project options (local/demo mode)")
    try:
        return firebase_admin.initialize_app(
            options={
                "projectId": PROJECT_ID,
                "storageBucket": STORAGE_BUCKET,
            }
        )
    except Exception as e:
        logger.warning(f"Could not initialize standard Firebase app: {e}")
        return None


def get_firestore_client() -> FirestoreClient:
    """Returns the Firestore Client instance."""
    app = get_firebase_app()
    if app:
        return firestore.client(app=app)
    return firestore.client()
