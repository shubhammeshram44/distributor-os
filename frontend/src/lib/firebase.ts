import { initializeApp, getApps, type FirebaseApp } from "firebase/app";
import { getAuth, type Auth } from "firebase/auth";

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
};

// Firebase is only usable when all required env vars are present. Missing
// or invalid config (e.g. a placeholder/blank NEXT_PUBLIC_FIREBASE_API_KEY)
// must NOT crash the app at import time - it previously threw an unhandled
// "Firebase: Error (auth/invalid-api-key)" that took down the whole /auth
// page. Instead, we degrade gracefully: `auth` is null and
// `isFirebaseConfigured` lets callers show a friendly error message.
export const isFirebaseConfigured = Boolean(
  firebaseConfig.apiKey && firebaseConfig.authDomain && firebaseConfig.projectId
);

let app: FirebaseApp | null = null;
let auth: Auth | null = null;

if (isFirebaseConfigured) {
  try {
    app = getApps().length ? getApps()[0] : initializeApp(firebaseConfig);
    auth = getAuth(app);
  } catch (err) {
    // Defensive: an invalid (but present) API key/config still throws from
    // initializeApp/getAuth. Never let this bubble up as an unhandled
    // runtime error - fall back to the "not configured" state instead.
    console.error("Firebase initialization failed:", err);
    app = null;
    auth = null;
  }
}

export { auth };
