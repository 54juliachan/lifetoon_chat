// 匯入 Firebase 模組
import { initializeApp } from "https://www.gstatic.com/firebasejs/12.6.0/firebase-app.js";
import { getAnalytics } from "https://www.gstatic.com/firebasejs/12.6.0/firebase-analytics.js";
import { getAuth, signInWithEmailAndPassword, createUserWithEmailAndPassword } 
from "https://www.gstatic.com/firebasejs/12.6.0/firebase-auth.js";

// ---------------------- Firebase 初始化 ----------------------
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
const analytics = getAnalytics(app);
const auth = getAuth(app);

// ---------------------- DOM 事件綁定 ----------------------
window.addEventListener("DOMContentLoaded", () => {
  const loginBtn = document.getElementById("loginBtn");
  const signupBtn = document.getElementById("signupBtn");

  loginBtn.addEventListener("click", handleLogin);
  signupBtn.addEventListener("click", handleSignup);
});

// ---------------------- 登入功能 ----------------------
function handleLogin() {
  const email = document.getElementById("email").value.trim();
  const password = document.getElementById("password").value;

  if (!email || !password) {
    alert("請輸入完整的 Email 與密碼");
    return;
  }

  signInWithEmailAndPassword(auth, email, password)
    .then((userCredential) => {
      console.log("登入成功", userCredential.user);
      alert("登入成功！");
      window.location.href = "/home.html"; // 登入成功後導到聊天頁
    })
    .catch((error) => {
      console.error("登入失敗", error.code, error.message);
      alert("登入失敗：" + error.message);
    });
}

// ---------------------- 註冊功能 ----------------------
function handleSignup() {
  const email = document.getElementById("email").value.trim();
  const password = document.getElementById("password").value;

  if (!email || !password) {
    alert("請輸入完整的 Email 與密碼");
    return;
  }

  createUserWithEmailAndPassword(auth, email, password)
    .then((userCredential) => {
      console.log("註冊成功", userCredential.user);
      alert("註冊成功！");
      window.location.href = "/home.html"; // 註冊成功後導到聊天頁
    })
    .catch((error) => {
      console.error("註冊失敗", error.code, error.message);
      alert("註冊失敗：" + error.message);
    });
}
