import { auth } from "./firebase-config.js";
import { onAuthStateChanged } from "https://www.gstatic.com/firebasejs/12.6.0/firebase-auth.js";

let currentUser = null;

onAuthStateChanged(auth, async (user) => {
  if (user) {
    currentUser = user;
    
    // 1. 載入歷史訊息
    await loadHistory();
    
    // 2. 觸發 AI 歡迎語
    triggerWelcome();

    // --- [新增：處理來自 home.html 的訊息] ---
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

async function triggerWelcome() {
    if (!currentUser) return;
    try {
        const token = await currentUser.getIdToken();
        const localTime = new Date().toLocaleString(); 
        const res = await fetch("/api/welcome", {
            method: "POST",
            headers: { 
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}` 
            },
            body: JSON.stringify({ local_time: localTime })
        });
        if (!res.ok) return;
        const data = await res.json();
        if (data.message && data.message.content) {
            addMessage(data.message.content, "ai");
        }
    } catch (err) {
        console.error("Welcome message system error:", err);
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

// --- [新增：處理結束聊天] ---
if (finishBtn) {
    finishBtn.addEventListener("click", async () => {
        if (!currentUser) return;
        finishBtn.disabled = true;
        finishBtn.textContent = "整理中...";
        try {
            const token = await currentUser.getIdToken();
            const res = await fetch("/api/summarize", {
                method: "POST",
                headers: { 
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${token}`
                }
            });
            if (!res.ok) throw new Error("分析失敗");
            const summaryData = await res.json();
            
            // 存入 localStorage 並清除前端訊息
            localStorage.setItem("card_summary", JSON.stringify(summaryData));
            if (messages) messages.innerHTML = "";
            
            window.location.href = "card.html";
        } catch (err) {
            console.error(err);
            alert("整理失敗");
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