# Firebase Project Setup Guide (100% Free Spark Plan)

This document provides step-by-step instructions for configuring Google Firebase services for the **Cloud-Based Student Assignment Submission & Feedback Portal**. 

> [!IMPORTANT]
> **Zero Cost Guarantee (Spark Plan)**:
> The Firebase **Spark Plan** is completely **free** and **requires no credit card or billing setup**.
> Firebase projects on the Spark plan **cannot automatically upgrade or incur charges** without explicit user upgrade to the Blaze plan. This project is architected to operate comfortably within all Spark plan daily free quotas.

---

## 📋 Manual Setup Steps in Firebase Console

Follow these steps directly in the [Firebase Console](https://console.firebase.google.com/):

### Step 1: Create a New Firebase Project
1. Open [https://console.firebase.google.com/](https://console.firebase.google.com/) and sign in with your Google account.
2. Click **"Add project"** (or **"Create a project"**).
3. Enter your project name (e.g., `student-assignment-portal`).
4. (Optional) Disable Google Analytics for simplicity, then click **"Create project"**.
5. Wait for the project initialization to finish and click **"Continue"**.

---

### Step 2: Enable Cloud Firestore Database (Native Mode)
1. In the left navigation menu, click **Build** > **Firestore Database**.
2. Click **"Create database"**.
3. **Database Location**: Choose a nearby multi-region or regional location (e.g., `nam5 (us-central)` or `asia-south1`).
4. **Security Rules**: Select **"Start in test mode"** for development (or production mode with rules configured).
5. Click **"Create"** / **"Enable"**.

---

### Step 3: Enable Firebase Storage (Object Storage)
1. In the left navigation menu, click **Build** > **Storage**.
2. Click **"Get started"**.
3. Select **"Start in test mode"** for development rules.
4. Keep the default Cloud Storage location and click **"Done"**.
5. Note your bucket address (e.g., `your-project-id.firebasestorage.app` or `your-project-id.appspot.com`).

---

### Step 4: Enable Firebase Authentication
1. In the left navigation menu, click **Build** > **Authentication**.
2. Click **"Get started"**.
3. Under the **"Sign-in method"** tab, select **"Email/Password"**.
4. Enable the first toggle (**Email/Password**). Leave "Email link (passwordless sign-in)" disabled.
5. Click **"Save"**.

---

### Step 5: Generate Admin SDK Service Account Key (Backend)
1. In the top left navigation, click the **Gear Icon (⚙️)** next to "Project Overview" > **Project settings**.
2. Navigate to the **"Service accounts"** tab.
3. Select **"Firebase Admin SDK"** and ensure **Python** is selected.
4. Click **"Generate new private key"**, then confirm by clicking **"Generate key"**.
5. A JSON file will download to your machine (e.g., `student-assignment-portal-firebase-adminsdk-xxxxx.json`).
6. Place this file safely inside your project (e.g., in `backend/serviceAccountKey.json`).
   > [!WARNING]
   > Make sure `serviceAccountKey.json` is listed in your `.gitignore` and **never** committed to version control.

---

### Step 6: Get Frontend Web App Config (Next.js)
1. In **Project settings** > **"General"** tab, scroll down to the **"Your apps"** section.
2. Click the Web icon (`</>`) to add a Web app.
3. Enter App nickname (e.g., `Assignment Portal Web`).
4. (Optional) Leave "Firebase Hosting" unchecked for now. Click **"Register app"**.
5. Copy the `firebaseConfig` keys into your `.env` file for the frontend:
   ```env
   NEXT_PUBLIC_FIREBASE_API_KEY=AIzaSy...
   NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
   NEXT_PUBLIC_FIREBASE_PROJECT_ID=your-project-id
   NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=your-project.firebasestorage.app
   NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=1234567890
   NEXT_PUBLIC_FIREBASE_APP_ID=1:1234567890:web:...
   ```

---

## 🛠️ Local Development with Firebase Emulators (Optional)
For offline local development and automated testing, you can use the Firebase Local Emulator Suite:
```bash
# Run Firestore emulator locally
export FIRESTORE_EMULATOR_HOST=localhost:8080
export FIREBASE_AUTH_EMULATOR_HOST=localhost:9099
export FIREBASE_STORAGE_EMULATOR_HOST=localhost:9199
```
The backend includes built-in fallback modes that connect seamlessly to both local emulators and live Firebase projects.
