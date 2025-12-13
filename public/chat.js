// public/chat.js
import { auth } from "./firebase-config.js"; // 匯入共用的 auth
import { onAuthStateChanged } from "https://www.gstatic.com/firebasejs/12.6.0/firebase-auth.js";

// 檢查使用者是否登入
let currentUser = null;

onAuthStateChanged(auth, (user) => {
  if (user) {
    currentUser = user;
    console.log("User is logged in:", user.email);
  } else {
    // 如果沒登入，強制導回首頁
    alert("請先登入！");
    window.location.href = "/";
  }
});

// ... (保留原本的 getTodayDate, addMessage 等 UI 函數) ...
function getTodayDate() {
    const today = new Date();
    const year = today.getFullYear();
    const month = (today.getMonth() + 1).toString().padStart(2, "0");
    const day = today.getDate().toString().padStart(2, "0");
    return `${year}-${month}-${day}`;
}

window.addEventListener("DOMContentLoaded", () => {
    const title = document.getElementById("chatTitle");
    if (title) title.textContent = getTodayDate();
});

const input = document.getElementById("userInput");
const btn = document.getElementById("sendBtn");
const messages = document.getElementById("chatMessages");

function addMessage(text, sender) {
    if (!messages) return;
    const bubble = document.createElement("div");
    bubble.classList.add("message", sender);
    bubble.textContent = text;
    messages.appendChild(bubble);
    messages.scrollTop = messages.scrollHeight;
}

// 核心修改：發送訊息時帶上 Token
async function aiReply(userText) {
  if (!currentUser) {
      addMessage("❌ 請先登入才能使用聊天功能", "ai");
      return;
  }

  try {
    // 1. 取得使用者的 ID Token (如果過期會自動刷新)
    const token = await currentUser.getIdToken();

    // 2. 發送請求到新的 FastAPI 接口
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { 
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}` // 帶上 Token
      },
      body: JSON.stringify({ message: userText })
    });

    if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || `Server Error: ${res.status}`);
    }

    const data = await res.json();
    const reply = data.message?.content || "AI 沒回應";
    addMessage(reply, "ai");

  } catch (err) {
    console.error(err);
    addMessage(`❌ 發生錯誤：${err.message}`, "ai");
  }
}

// 事件監聽
if (btn) btn.addEventListener("click", sendMessage);
if (input) {
    input.addEventListener("keypress", (e) => {
      if (e.key === "Enter") sendMessage();
    });
}

function sendMessage() {
  const text = input.value.trim();
  if (!text) return;
  addMessage(text, "user");
  input.value = "";
  aiReply(text);
}