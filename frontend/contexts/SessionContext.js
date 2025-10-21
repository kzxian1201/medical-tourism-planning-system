import React, { createContext, useState, useEffect, useCallback, useRef } from 'react';
import { initializeApp, getApps, getApp } from 'firebase/app';
import { getAuth, onAuthStateChanged, signOut as firebaseSignOut, signInWithEmailAndPassword, createUserWithEmailAndPassword, sendPasswordResetEmail as firebaseSendPasswordResetEmail, EmailAuthProvider, reauthenticateWithCredential } from 'firebase/auth';
import { getFirestore, doc, setDoc, getDoc, collection, query, where, orderBy, getDocs, Timestamp, increment, updateDoc, deleteDoc, runTransaction } from 'firebase/firestore';
import { onSnapshot } from 'firebase/firestore';
import { getStorage, ref, uploadBytes, getDownloadURL } from 'firebase/storage'; 

// --- Firebase Configuration from Environment Variables ---
const firebaseConfig = {
    apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
    authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
    projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
    storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
    messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
    appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
    measurementId: process.env.NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID,
};

// Ensure the Firebase app is initialized only once
const appId = process.env.NEXT_PUBLIC_FIREBASE_APP_ID || 'default-app-id-from-env';

// initialAuthToken is used for custom token authentication, if provided
const initialAuthToken = process.env.NEXT_PUBLIC_FIREBASE_AUTH_TOKEN || null;

// --- Firebase Initialization ---
let firebaseAppInstance;
let dbInstance;
let authInstance;
let storageInstance; 

try {
    // Check if Firebase apps are already initialized
    if (!getApps().length) { // If no apps are initialized
        // Check if the firebaseConfig has the necessary fields
        if (firebaseConfig.apiKey && firebaseConfig.projectId && firebaseConfig.appId) {
            firebaseAppInstance = initializeApp(firebaseConfig);
            console.log("Firebase initialized successfully from environment variables.");
        } else {
            console.warn("Firebase config is incomplete from environment variables. Firestore features will be disabled.");
        }
    } else {
        // Get the already initialized app instance
        firebaseAppInstance = getApp();
        console.log("Firebase app already initialized.");
    }

    // Get Firestore and Auth instances
    if (firebaseAppInstance) {
        dbInstance = getFirestore(firebaseAppInstance);
        authInstance = getAuth(firebaseAppInstance);
        storageInstance = getStorage(firebaseAppInstance);
    } else {
        dbInstance = null; // Ensure dbInstance is null if app initialization failed
        authInstance = null;
        storageInstance = null;
    }
} catch (error) {
    console.error("Failed to initialize Firebase:", error);
    dbInstance = null;
    authInstance = null;
    storageInstance = null;
}

// Create the Session Context
export const SessionContext = createContext(null);

// --- Helper Hook for Debouncing ---
function useDebounce(value, delay) {
    const [debouncedValue, setDebouncedValue] = useState(value);

    useEffect(() => {
        const handler = setTimeout(() => {
            setDebouncedValue(value);
        }, delay);

        return () => {
            clearTimeout(handler);
        };
    }, [value, delay]);

    return debouncedValue;
}

// Define a function to get an initial session state, ensuring a new sessionId and timestamp
const getInitialSessionState = (userId, profileData = {}) => ({
    sessionId: null, 
    userId,
    current_stage: "initial_query",
    chat_history: [],
    profileData: {...profileData, },
    medicalDetails: {
        purpose: '',
        destinationCountry: [],
        budgetRange: [0, 1000000],
        departureDate: '',
        travelFlexibility: '',
        urgencyLevel: '',
        accompanyingGuestsPresence: '',
        accompanyingGuestsCount: 0,
        preferredLanguageOfCare: [],
        hospital: null,
    },
    travelArrangements: {
        departureCity: '',
        returnDate: '',
        flightPreferences: [],
        accommodationRequirements: [],
        preferredAccommodationStarRating: [],
        visaAssistanceNeeded: '',
        flight: null,
        accommodation: null,
    },
    localLogistics: {
        airportPickupService: '',
        localTransportationNeeds: [],
        additionalLocalServices: [],
        hasSpecificDietaryNeeds: '',
        specificDietaryPreferences: [],
        localSimCardAssistance: '',
        leisureActivityInterest: [],
    },
    currentMedicalOptions: [],
    currentFlightOptions: [],
    currentAccommodationOptions: [],
    final_report: null,
    timestamp: null,
});

// SessionProvider Component manages global session state, Firebase authentication, and persistence of session data to Firestore.
export const SessionProvider = ({ children }) => {
    // Initialize state with a temporary sessionId and null userId until auth is ready
    const [sessionState, setSessionState] = useState(() => getInitialSessionState(null));
    const [authReady, setAuthReady] = useState(false);
    const [firebaseUserId, setFirebaseUserId] = useState(null); // Actual Firebase UID or generated anonymous ID
    const [userEmail, setUserEmail] = useState(null);
    // State to track if the initial session load logic has completed
    const [initialSessionLoaded, setInitialSessionLoaded] = useState(false);
    // Ref to store the previous sessionId to detect when a new session has started
    const prevSessionIdRef = useRef(null);

    // --- New State for UI Feedback and Concurrency Management ---
    const [isLoading, setIsLoading] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [profileData, setProfileData] = useState(null);
    const [isProfileLoading, setIsProfileLoading] = useState(true);

    const hasStartedPlanRef = useRef(false);

    // Debounce the sessionState before saving to Firestore
    const debouncedSessionState = useDebounce(sessionState, 1000); // Debounce for 1 second

    // Function to update session state that will also trigger Firestore save
    const updateSessionState = useCallback((newState) => {
        setSessionState(prev => {
            return { ...prev, ...newState, timestamp: Timestamp.now() };
        });
    }, []);

    const safeLocalStorage = {
        get: (key) => (typeof window !== 'undefined' ? localStorage.getItem(key) : null),
        set: (key, value) => { if (typeof window !== 'undefined') localStorage.setItem(key, value); },
        remove: (key) => { if (typeof window !== 'undefined') localStorage.removeItem(key); },
    };

    // Utility: clear only session-related localStorage keys
    const clearSessionLocalStorage = () => {
        if (typeof window === 'undefined') return;
            Object.keys(localStorage).forEach((key) => {
                if (key.startsWith("lastActiveSessionId_")) {
                    localStorage.removeItem(key);
                }
        });
    };
        
    // new function to delete a session by its planId
    const deleteSession = async (planId) => {
        if (!firebaseUserId  || !planId) return false;
        try {
            const docRef = doc(dbInstance, `artifacts/${appId}/users/${firebaseUserId}/sessions`, planId);
            const docSnap = await getDoc(docRef);

            if (!docSnap.exists()) {
                console.warn("Plan not found, cannot delete:", planId);
                return false;
            }

            await deleteDoc(docRef);
            return true;
        } catch (error) {
            console.error("Error deleting session:", error);
            return false;
        }
    };

    // Function to handle Firebase Auth errors and convert them to user-friendly messages
    const handleAuthError = useCallback((error) => {
        switch (error.code) {
            case 'auth/wrong-password':
            case 'auth/invalid-credential':
                return 'Wrong email or password. Please try again!';
            case 'auth/user-not-found':
                return 'There is no account registered with this email address!';
            case 'auth/email-already-in-use':
                return 'This email address has already been registered. Please try logging in or using a different email address!';
            case 'auth/invalid-email':
                return 'The email address format is invalid. Please check and try again!';
            case 'auth/weak-password':
                return 'The password is too weak. Please use a password of at least 6 characters!';
            case 'auth/too-many-requests':
                return 'Too many failed login attempts. Please try again later!';
            case 'auth/requires-recent-login':
                return 'This operation requires a recent login. Please log in again and try again!';
            default:
                console.error("Unhandled Firebase Auth error:", error);
                return 'An unexpected error occurred. Please try again later!';
        }
    }, []);

    // New function to handle email/password registration
    const register = useCallback(async (email, password) => {
        if (!authInstance) {
            return { success: false, error: "Firebase Auth not available." };
        }
        try {
            const userCredential = await createUserWithEmailAndPassword(authInstance, email, password);
            const user = userCredential.user;
            console.log("User registered with email:", user.email);
            setFirebaseUserId(user.uid);
            return { success: true };
        } catch (error) {
            console.error("Error registering:", error.message);
            return { success: false, error: handleAuthError(error) };
        }
    }, [handleAuthError]);

    // New function to handle email/password sign-in
    const signIn = useCallback(async (email, password) => {
        if (!authInstance) {
            return { success: false, error: "Firebase Auth not available." };
        }

        try {
            const userCredential = await signInWithEmailAndPassword(authInstance, email, password);
            setFirebaseUserId(userCredential.user.uid);
            return { success: true };
        } catch (authError) {
            const friendlyError = handleAuthError(authError);
            return { success: false, error: friendlyError };
        }
    }, [authInstance, handleAuthError]);

    // New function to handle forgotten passwords
    const sendPasswordResetEmail = useCallback(async (email) => {
        if (!authInstance) {
            return { success: false, error: "Firebase Auth not available." };
        }
        try {
            await firebaseSendPasswordResetEmail(authInstance, email);
            console.log("Password reset email sent to:", email);
            return { success: true, message: 'A password reset link has been sent to your email!' };
        } catch (error) {
            console.error("Error sending password reset email:", error.message);
            return { success: false, error: handleAuthError(error)  };
        }
    }, [authInstance, handleAuthError]);

    // New function to handle sign out
    const signOut = useCallback(async () => {
        if (!authInstance) {
            console.warn("Auth instance not available. Cannot sign out.");
            return;
        }
        try {
            await firebaseSignOut(authInstance);
            console.log("User signed out. onAuthStateChanged will handle state change.");
            clearSessionLocalStorage();
        } catch (error) {
            console.error("Error signing out:", error);
        }
    }, [firebaseUserId]);

    // Effect to handle agent response and update session state accordingly
    const handleAgentResponse = useCallback(async (backendResponse, planSessionId = sessionState.sessionId) => {
        console.log("CRITICAL DEBUG: The raw backendResponse is:", backendResponse);

        // Step 1: Log the raw response received
        const rawResponseText = typeof backendResponse === 'string' ? backendResponse : JSON.stringify(backendResponse);
        console.log("Raw backend response received:", rawResponseText);

        // Step 2: Check for the specific "hi" or "hello" string response
        if (rawResponseText.trim().toLowerCase() === 'hi' || rawResponseText.trim().toLowerCase() === 'hello') {
            const errorMessage = "Invalid backend response received: Next.js API route is not properly proxying the request and is returning a default string. Please check the `agent-conversation.js` file and the backend server status.";
            console.error(errorMessage);
            setSessionState(prev => ({
            ...prev,
            chat_history: [...(prev.chat_history || []), {
                id: Timestamp.now().toMillis().toString() + "-error",
                sender: "agent",
                type: "text",
                content: { prompt: "Sorry, there was a problem with our service. The API returned an unexpected response." },
                timestamp: Timestamp.now(),
            }]
            }));
            setIsLoading(false);
            setIsSaving(false);
            return { success: false, error: errorMessage };
        }
        if (!backendResponse || typeof backendResponse !== 'object') {
            console.error("Invalid backend response received:", backendResponse);
            // Display a generic error message to the user
            setSessionState(prev => ({
                ...prev,
                chat_history: [...(prev.chat_history || []), {
                    id: Timestamp.now().toMillis().toString() + "-error",
                    sender: "agent",
                    type: "text",
                    content: { prompt: "Sorry, there was a problem receiving a valid response from the planning service." },
                    timestamp: Timestamp.now(),
                }]
            }));
            setIsLoading(false); // Make sure to turn off any loading indicators
            setIsSaving(false);  // Make sure to turn off any saving indicators
            return { success: false, error: "Invalid backend response." };
        }

        if (!dbInstance || !firebaseUserId || !planSessionId) {
            console.warn("Firestore, UserID, or SessionID missing. Aborting write operation.");
            return { success: false, error: "Service unavailable." };
        }
        console.log("Raw backend response:", backendResponse);

        setIsSaving(true); 
        try {
            let { agent_response, updated_session_state } = backendResponse;

            if (!agent_response && backendResponse?.message_type) {
                agent_response = {
                    message_type: backendResponse.message_type,
                    content: backendResponse.content
                };
                updated_session_state = backendResponse.updated_session_state || {};
            }

            if (!agent_response || !agent_response.content || typeof agent_response.content !== "object") {
                console.warn("Backend response invalid, applying fallback.", backendResponse);
                agent_response = {
                    message_type: "text",
                    content: { prompt: typeof backendResponse === "string" ? backendResponse : "Sorry, the agent response was invalid." }
                };
                updated_session_state = updated_session_state || {};
            }

            const newTimestamp = Timestamp.now();
            const newAgentMessage = {
                id: newTimestamp.toMillis().toString() + "-agent",
                sender: "agent",
                type: agent_response.message_type,
                content: agent_response.content,
                timestamp: newTimestamp,
            };

            const sessionDocRef = doc(dbInstance, `artifacts/${appId}/users/${firebaseUserId}/sessions`, planSessionId);

            await runTransaction(dbInstance, async (transaction) => {
                const sessionDoc = await transaction.get(sessionDocRef);

                let currentData;
                if (!sessionDoc.exists()) {
                    console.warn("Session document does not exist, creating new one.");
                    currentData = {
                        chat_history: [],
                        session_state: {},
                        timestamp: newTimestamp,
                    };
                } else {
                    currentData = sessionDoc.data();
                }

                const newChatHistory = [...(currentData.chat_history || []), newAgentMessage];

                const updatedState = {
                    ...currentData,
                    ...(updated_session_state || {}),
                    chat_history: newChatHistory,
                    timestamp: newTimestamp,
                };

                transaction.set(sessionDocRef, updatedState, { merge: true });
            });

            console.log("Session updated with new agent response.");
            return { success: true };
        } catch (error) {
            console.error("Error handling agent response:", error.message, error.code, "Full error object:", error);

            setSessionState(prev => {
                const newChatHistory = [...(prev.chat_history || []), {
                    id: Timestamp.now().toMillis().toString() + "-error",
                    sender: "agent",
                    type: "text",
                    content: { prompt: "Sorry, there was a problem processing your request." },
                    timestamp: Timestamp.now(),
                }];
                return { ...prev, chat_history: newChatHistory };
            });

            return { success: false, error: error.message };
        } finally {
            setIsSaving(false); 
        }
    }, [dbInstance, firebaseUserId, sessionState.sessionId]);
    
    // Function to load a historical plan by its sessionId
    const loadPlan = useCallback(async (planSessionId, currentUserId) => {
        if (!dbInstance || !currentUserId || !planSessionId) {
            console.warn("Firestore, UserId, or PlanId not available to load plan.");
            return false; // Indicate failure
        }
        try {
            const planDocRef = doc(dbInstance, `artifacts/${appId}/users/${currentUserId}/sessions`, planSessionId);
            const docSnap = await getDoc(planDocRef);
            if (docSnap.exists()) {
                const loadedData = docSnap.data();
                setSessionState(loadedData && typeof loadedData === 'object' ? loadedData : getInitialSessionState(firebaseUserId));
                localStorage.setItem(`lastActiveSessionId_${currentUserId}`, planSessionId); // Save to local storage
                console.log("Loaded historical plan:", planSessionId);
                return true; // Indicate success
            } else {
                console.warn("Historical plan not found:", planSessionId);
                localStorage.removeItem(`lastActiveSessionId_${currentUserId}`);
                return false; // Indicate failure
            }
        } catch (error) {
            console.error("Error loading historical plan:", error);
            return false; // Indicate failure
        }
    }, [dbInstance, firebaseUserId]);

    // Function to start a new plan, resetting session state and creating a new sessionId
    const startNewPlan = useCallback(async (profileDataFromContext = profileData) => {
        if (!authReady || !firebaseUserId) {
            console.warn("Auth not ready or user not authenticated. Cannot start new plan.");
            return;
        }
        setIsLoading(true);
        const newSessionId = typeof crypto?.randomUUID === 'function'
            ? crypto.randomUUID()
            : `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
        const newSession = { 
            ...getInitialSessionState(firebaseUserId, profileDataFromContext),
            sessionId: newSessionId
        };
        try {
            const response = await fetch('/api/agent-conversation', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: newSession.sessionId,
                    user_input: 'start_new_plan',
                    current_stage: newSession.current_stage,
                    chat_history: newSession.chat_history,
                    session_state: {
                        ...newSession,
                        profileData: profileDataFromContext
                    }
                }),
            });
            const data = await response.json();  
            // Pass the new sessionId directly to handleAgentResponse, or ensure it's in a shared state
            await handleAgentResponse(data, newSession.sessionId); // Pass new sessionId
            localStorage.setItem(`lastActiveSessionId_${firebaseUserId}`, newSession.sessionId);
            console.log("Started a new plan:", newSession.sessionId);
        } catch (error) {
            console.error("Error starting new plan:", error);
            updateSessionState({
                chat_history: [{
                        id: Timestamp.now().toMillis().toString() + "-error",
                        sender: "agent",
                        type: "text",
                        content: {prompt:"Unable to start a new planning session, please try again later."},
                        timestamp: Timestamp.now(),
                    }],
            });
        } finally {
            setIsLoading(false);
        }
    },[firebaseUserId, handleAgentResponse, profileData, authReady]);

    // Function to fetch all user's historical plans
    const fetchUserPlans = useCallback(async () => {
        if (!dbInstance || !firebaseUserId) {
            console.warn("Firestore or UserId not available to fetch user plans.");
            return [];
        }
        try {
            const plansCollectionRef = collection(dbInstance, `artifacts/${appId}/users/${firebaseUserId}/sessions`);
            const q = query(plansCollectionRef, orderBy("timestamp", "desc")); // Order by timestamp descending
            const querySnapshot = await getDocs(q);
            const plansList = querySnapshot.docs.map(doc => ({
                id: doc.id, // Firestore document ID is the sessionId
                ...doc.data()
            }));
            console.log("Fetched user plans:", plansList);
            return plansList;
        } catch (error) {
            console.error("Error fetching user plans:", error);
            return [];
        }
    }, [firebaseUserId]);

    // New function to fetch user profile data
    const fetchUserProfile = useCallback(async (userId) => {
        setIsProfileLoading(true);
        if (!dbInstance || !userId) {
            console.error("Firestore instance or userId is not available.");
            setIsProfileLoading(false);
            return null; // Return null or an empty object to indicate no data
        }
        try {
            const userProfileRef = doc(dbInstance, `artifacts/${appId}/users/${userId}/profile`, 'public');
            const docSnap = await getDoc(userProfileRef);
            if (docSnap.exists()) {
                setProfileData(docSnap.data());
                return docSnap.data();
            } else {
                console.log("No profile data found for this user.");
                setProfileData({});
                return {}; // Return null if no data exists
            }
        } catch (error) {
            console.error("Error fetching user profile:", error);
            setProfileData({});
            return {};
        } finally {
            setIsProfileLoading(false);
        }
    }, [dbInstance, appId]);

    // New function to save or update user profile data
    const saveUserProfile = useCallback(async (uid, profileData) => {
        if (!uid) throw new Error("User ID is required to save profile.");
        if (!dbInstance) return false;
        setIsSaving(true);
        try {
            const userDocRef = doc(dbInstance, 'artifacts', appId, 'users', uid, 'profile', 'public');
            await setDoc(userDocRef, profileData, { merge: true });
            return true;
        } catch (error) {
            console.error("Error saving profile:", error);
            return false;
        } finally {
            setIsSaving(false);
        }
    }, [dbInstance, appId]);

    // New function to delete user profile
    const deleteUserProfile = useCallback(async (uid) => {
        if (!uid) throw new Error("User ID is required to delete profile.");
        if (!dbInstance) return false;

        setIsSaving(true);
        try {
            const userProfileDocRef = doc(dbInstance, 'artifacts', appId, 'users', uid, 'profile', 'public');
            await deleteDoc(userProfileDocRef);
            return true;
        } catch (error) {
            console.error("Error deleting profile:", error);
            return false;
        } finally {
            setIsSaving(false);
        }
    }, [dbInstance, appId]);
    
    const uploadProfilePhoto = useCallback(async (uid, file) => {
        if (!uid || !file || !storageInstance) return null;
        try {
            const storageRef = ref(storageInstance, `profile_photos/${uid}`);
            const uploadResult = await uploadBytes(storageRef, file);
            const photoURL = await getDownloadURL(uploadResult.ref);
            return photoURL;
        } catch (error) {
            console.error("Error uploading profile photo:", error);
            return null;
        }
    }, [storageInstance]);

    const reauthenticateUser = async (email, password) => {
        try {
            const credential = EmailAuthProvider.credential(email, password);
            await reauthenticateWithCredential(authInstance.currentUser, credential);
            return { success: true };
        } catch (error) {
            console.error("Reauthentication failed:", error);
            return { success: false, error: handleAuthError(error) };
        }
    };

    const deleteAccount = useCallback(async (email, password) => {
        if (!authInstance || !dbInstance || !firebaseUserId) {
            return { success: false, error: "Firebase services or user ID not available." };
        }

        try {
            const reauth = await reauthenticateUser(email, password);
            if (!reauth.success) return reauth;

            const sessionsCollectionRef = collection(dbInstance, `artifacts/${appId}/users/${firebaseUserId}/sessions`);
            const querySnapshot = await getDocs(query(sessionsCollectionRef));
            await Promise.all(querySnapshot.docs.map(d => deleteDoc(doc(sessionsCollectionRef, d.id))));
            await deleteDoc(doc(dbInstance, 'artifacts', appId, 'users', firebaseUserId, 'profile', 'public'));

            await authInstance.currentUser.delete();
            clearSessionLocalStorage();

            return { success: true };
        } catch (error) {
            console.error("Error deleting account:", error);
            return { success: false, error: handleAuthError(error) };
        }
    }, [authInstance, dbInstance, firebaseUserId]);

    // Effect to handle Firebase Authentication and initial session state loading
    useEffect(() => {
        if (!authInstance) {
            console.warn("Firebase Auth not available. Running without authentication.");
            setAuthReady(true);
            setInitialSessionLoaded(true);
            return;
        }

        const unsubscribe = onAuthStateChanged(authInstance, async (user) => {
            if (user) {
                const currentUserId = user.uid;
                setFirebaseUserId(currentUserId);
                setUserEmail(user.email);
                console.log("User authenticated:", currentUserId);

                await fetchUserProfile(currentUserId);

                const lastActiveSessionId = safeLocalStorage.get(`lastActiveSessionId_${currentUserId}`);
                if (lastActiveSessionId) {
                    const loaded = await loadPlan(lastActiveSessionId, currentUserId);
                    if (!loaded) {
                        console.warn("Could not load last active session. Clearing cache and starting a new one.");
                        safeLocalStorage.remove(`lastActiveSessionId_${currentUserId}`);
                    } else {
                        safeLocalStorage.set(`lastActiveSessionId_${currentUserId}`, lastActiveSessionId);
                    }
                } else {
                    console.log("No last active session. A new plan will be started if needed.");
                    setSessionState(getInitialSessionState(currentUserId));
                }
            } else {
                console.log("No user authenticated. Clearing session.");
                setFirebaseUserId(null);
                setUserEmail(null);
                setSessionState(getInitialSessionState(null));
                clearSessionLocalStorage();
                setProfileData(null);
            }
            
            setInitialSessionLoaded(true);
            setAuthReady(true);
        });

        return () => unsubscribe();
    }, [authInstance, fetchUserProfile, loadPlan]);

    useEffect(() => {
        if (authReady && initialSessionLoaded && firebaseUserId && !isProfileLoading && !sessionState?.sessionId && !hasStartedPlanRef.current) {
            console.log("All conditions met. Starting a new plan automatically.");
            hasStartedPlanRef.current = true;
            startNewPlan(profileData);
        }
    }, [authReady, firebaseUserId, sessionState?.sessionId, isProfileLoading, profileData, startNewPlan]);

    // Effect to sync session state in real-time from Firestore
    useEffect(() => {
        if (authReady && dbInstance && firebaseUserId && sessionState.sessionId) {
            const sessionDocRef = doc(
                dbInstance,
                `artifacts/${appId}/users/${firebaseUserId}/sessions`,
                sessionState.sessionId
            );

            const unsubscribe = onSnapshot(sessionDocRef, (docSnap) => {
                if (docSnap.exists()) {
                    const remoteData = docSnap.data();

                    setSessionState((prev) => {
                        // Avoid infinite loop: update only when remote data is newer than local data
                        // and when we are not currently saving locally
                        if (
                            !isSaving &&
                            (remoteData.timestamp?.seconds > prev.timestamp?.seconds ||
                            (
                                remoteData.timestamp?.seconds === prev.timestamp?.seconds &&
                                remoteData.timestamp?.nanoseconds > prev.timestamp?.nanoseconds
                            ))
                        ) {
                            console.log("Remote update received, merging session state.");
                            return { ...prev, ...remoteData };
                        }
                        return prev;
                    });
                }
            });

            return () => unsubscribe();
        }
    }, [authReady, firebaseUserId, sessionState.sessionId, dbInstance, isSaving]);

    return (
        <SessionContext.Provider value={{
            sessionState, updateSessionState, deleteSession, handleAgentResponse, userId: firebaseUserId, userEmail, authReady, startNewPlan,
            fetchUserPlans, loadPlan, signIn, register, signOut, sendPasswordResetEmail, authInstance,
            fetchUserProfile, saveUserProfile, deleteUserProfile, uploadProfilePhoto, deleteAccount,
            isLoading, isSaving, profileData, isProfileLoading
        }}>
            {children}
        </SessionContext.Provider>
    );
};