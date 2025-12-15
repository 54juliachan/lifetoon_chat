import { auth } from "./firebase-config.js";
import { onAuthStateChanged } from "https://www.gstatic.com/firebasejs/12.6.0/firebase-auth.js";

let currentUser = null;

onAuthStateChanged(auth, async (user) => {
  if (user) {
    currentUser = user;
    console.log("User is logged in:", user.email);
    
    // 1. 先載入歷史訊息
    await loadHistory();
    
    // 2. 載入完畢後，觸發 AI 主動問候
    triggerWelcome();
    
  } else {
    // 未登入則導回首頁
    // alert("請先登入！"); // 可視需求決定是否要跳窗
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

function addMessage(text, sender) {
    if (!messages) return;
    const bubble = document.createElement("div");
    bubble.classList.add("message", sender);
    bubble.textContent = text;
    messages.appendChild(bubble);
    messages.scrollTop = messages.scrollHeight;
}

// 載入歷史紀錄
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

// [新增] 觸發歡迎訊息
async function triggerWelcome() {
    if (!currentUser) return;

    // 簡單防呆：如果最後一則訊息已經是 AI 說的話，且距離現在很近，避免重複打招呼
    // 若希望每次重整都打招呼，可保持此段註解
    /* const lastMsg = messages.lastElementChild;
    if (lastMsg && lastMsg.classList.contains('ai')) {
         console.log("AI recently spoke, skipping welcome.");
         return; 
    }
    */

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

        // --- [錯誤處理修正] ---
        if (!res.ok) {
            // 嘗試讀取後端回傳的錯誤詳情，方便在 Console 除錯
            const errorData = await res.json().catch(() => ({})); 
            console.error("Welcome API Error Details:", errorData);
            // 歡迎訊息失敗通常不需跳 alert 或是顯示在聊天室，避免嚇到用戶
            return;
        }
        // -------------------

        const data = await res.json();
        // 顯示 AI 的歡迎語
        if (data.message && data.message.content) {
            addMessage(data.message.content, "ai");
        }
    } catch (err) {
        console.error("Welcome message system error:", err);
    }
}

// AI 回覆 (聊天核心功能)
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

    // --- [錯誤處理修正] ---
    if (!res.ok) {
        // 嘗試讀取後端回傳的錯誤詳情
        const errorData = await res.json().catch(() => ({})); 
        console.error("Chat API Error Details:", errorData); // 在 Console 顯示詳細錯誤
        
        // 拋出詳細錯誤訊息，以便在下方 catch 區塊捕捉並顯示在聊天視窗
        const errorMessage = errorData.detail || errorData.error || `Server Error (${res.status})`;
        throw new Error(errorMessage);
    }
    // -------------------

    const data = await res.json();
    addMessage(data.message?.content, "ai");

  } catch (err) {
    console.error("aiReply execution error:", err);
    // 將錯誤顯示在聊天視窗中，讓你知道發生了什麼事
    addMessage("❌ 錯誤：" + err.message, "ai");
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
  // 呼叫後端 API
  aiReply(text);
}