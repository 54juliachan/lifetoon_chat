// public/firebase-config.js
import { initializeApp } from "https://www.gstatic.com/firebasejs/12.6.0/firebase-app.js";
import { getAuth } from "https://www.gstatic.com/firebasejs/12.6.0/firebase-auth.js";

const firebaseConfig = {
  apiKey: "AIzaSyC6CUxG-B1ZkuFBk1zAGp1I2-0n3KilY6w",
  authDomain: "lifetoon-chat.firebaseapp.com",
  projectId: "lifetoon-chat",
  storageBucket: "lifetoon-chat.firebasestorage.app",
  messagingSenderId: "962298495930",
  appId: "1:962298495930:web:388d5cd407728533955383",
  measurementId: "G-8ZW9TZZ2XS"
};

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);