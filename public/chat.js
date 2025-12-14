// public/chat.js
import { auth } from "./firebase-config.js";
import { onAuthStateChanged } from "https://www.gstatic.com/firebasejs/12.6.0/firebase-auth.js";

let currentUser = null;

onAuthStateChanged(auth, async (user) => {
  if (user) {
    currentUser = user;
    console.log("User is logged in:", user.email);
    
    // 1. 先載入歷史訊息
    await loadHistory();
    
    // 2. [新增] 載入完畢後，觸發 AI 主動問候
    triggerWelcome();
    
  } else {
    alert("請先登入！");
    window.location.href = "/";
  }
});

// ... (getTodayDate, addMessage 等 UI 函數保持不變) ...
function getTodayDate() {
    const today = new Date();
    return `${today.getFullYear()}-${(today.getMonth() + 1).toString().padStart(2, "0")}-${today.getDate().toString().padStart(2, "0")}`;
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

// ... (loadHistory 保持不變) ...
async function loadHistory() {
    if (!currentUser) return;
    try {
        const token = await currentUser.getIdToken();
        const res = await fetch("/api/history", {
            headers: { "Authorization": `Bearer ${token}` }
        });
        if (res.ok) {
            const data = await res.json();
            messages.innerHTML = ""; 
            data.history.forEach(msg => {
                addMessage(msg.content, msg.sender);
            });
        }
    } catch (err) {
        console.error("Failed to load history:", err);
    }
}

// [新增] 觸發歡迎訊息
async function triggerWelcome() {
    if (!currentUser) return;

    // 簡單防呆：如果最後一則訊息已經是 AI 說的話，且距離現在很近（例如幾秒前），
    // 可能是頁面剛剛重新整理，避免 AI 一直重複打招呼（可依需求決定是否保留此檢查）
    /* const lastMsg = messages.lastElementChild;
    if (lastMsg && lastMsg.classList.contains('ai')) {
        // 這裡可以加入時間判斷邏輯，目前先讓它每次都打招呼
    }
    */

    try {
        const token = await currentUser.getIdToken();
        // 取得使用者當地時間字串，例如 "下午 8:00:00"
        const localTime = new Date().toLocaleString(); 

        const res = await fetch("/api/welcome", {
            method: "POST",
            headers: { 
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}` 
            },
            body: JSON.stringify({ local_time: localTime })
        });

        if (res.ok) {
            const data = await res.json();
            // 顯示 AI 的歡迎語
            addMessage(data.message.content, "ai");
        }
    } catch (err) {
        console.error("Welcome message error:", err);
    }
}

// ... (aiReply, sendMessage 等原有傳訊功能保持不變) ...
async function aiReply(userText) {
  if (!currentUser) return;

  try {
    const token = await currentUser.getIdToken();
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { 
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
      },
      body: JSON.stringify({ message: userText })
    });
    // ... (錯誤處理與顯示邏輯保持不變) ...
    if (!res.ok) throw new Error("API Error");
    const data = await res.json();
    addMessage(data.message?.content, "ai");
  } catch (err) {
    console.error(err);
    addMessage("❌ 錯誤：" + err.message, "ai");
  }
}

// ... (事件監聽保持不變) ...
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