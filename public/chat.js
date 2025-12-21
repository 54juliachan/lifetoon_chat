import { auth } from "./firebase-config.js";
import { onAuthStateChanged } from "https://www.gstatic.com/firebasejs/12.6.0/firebase-auth.js";

let currentUser = null;

onAuthStateChanged(auth, async (user) => {
  if (user) {
    currentUser = user;
    
    // 1. 載入歷史訊息
    await loadHistory();
    
    // 2. 處理來自 home.html 的訊息
    const pendingMessage = localStorage.getItem("pendingMessage");
    if (pendingMessage) {
      localStorage.removeItem("pendingMessage");
      addMessage(pendingMessage, "user");
      aiReply(pendingMessage);
    }
  } else {
    window.location.href = "/";
  }
});

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
const finishBtn = document.querySelector(".finish-chat");

function addMessage(text, sender) {
    if (!messages) return;
    const bubble = document.createElement("div");
    bubble.classList.add("message", sender);
    bubble.textContent = text;
    messages.appendChild(bubble);
    messages.scrollTop = messages.scrollHeight;
}

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
            if (data.history && Array.isArray(data.history)) {
                data.history.forEach(msg => {
                    addMessage(msg.content, msg.sender);
                });
            }
        }
    } catch (err) {
        console.error("Failed to load history:", err);
    }
}

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
    if (!res.ok) {
        const errorData = await res.json().catch(() => ({})); 
        const errorMessage = errorData.detail || errorData.error || `Server Error (${res.status})`;
        throw new Error(errorMessage);
    }
    const data = await res.json();
    addMessage(data.message?.content, "ai");
  } catch (err) {
    addMessage("❌ 錯誤：" + err.message, "ai");
  }
}

// --- [結束聊天：分析並刪除紀錄] ---
if (finishBtn) {
    finishBtn.addEventListener("click", async () => {
        if (!currentUser) return;
        
        const confirmFinish = confirm("確定要結束聊天嗎？這將會分析內容並清空目前的對話紀錄。");
        if (!confirmFinish) return;

        finishBtn.disabled = true;
        finishBtn.textContent = "整理並清空紀錄中...";
        
        try {
            const token = await currentUser.getIdToken();
            const res = await fetch("/api/summarize", {
                method: "POST",
                headers: { 
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${token}`
                }
            });
            
            if (!res.ok) throw new Error("分析或刪除失敗");
            const summaryData = await res.json();
            
            // 1. 將分析結果存入 localStorage
            localStorage.setItem("card_summary", JSON.stringify(summaryData));
            
            // 2. 清除前端畫面訊息
            if (messages) messages.innerHTML = "";
            
            // 3. 跳轉
            window.location.href = "card.html";
        } catch (err) {
            console.error(err);
            alert("處理失敗，請稍後再試。");
            finishBtn.disabled = false;
            finishBtn.textContent = "結束聊天";
        }
    });
}

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