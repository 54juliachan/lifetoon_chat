// public/chat.js
import { auth } from "./firebase-config.js";
import { onAuthStateChanged } from "https://www.gstatic.com/firebasejs/12.6.0/firebase-auth.js";

// 檢查使用者是否登入
let currentUser = null;

onAuthStateChanged(auth, async (user) => { // [修改] 加上 async
  if (user) {
    currentUser = user;
    console.log("User is logged in:", user.email);
    await loadHistory(); // [新增] 登入後載入歷史訊息
  } else {
    alert("請先登入！");
    window.location.href = "/";
  }
});

// ... (getTodayDate, window event listener 保持不變) ...
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
    bubble.textContent = text; // [注意] 這裡可以考慮支援 markdown 解析，看需求
    messages.appendChild(bubble);
    messages.scrollTop = messages.scrollHeight;
}

// [新增] 載入歷史訊息函數
async function loadHistory() {
    if (!currentUser) return;
    
    try {
        const token = await currentUser.getIdToken();
        const res = await fetch("/api/history", {
            headers: { "Authorization": `Bearer ${token}` }
        });
        
        if (res.ok) {
            const data = await res.json();
            // 清空目前的顯示 (避免重複)，或者也可以保留
            messages.innerHTML = ""; 
            
            data.history.forEach(msg => {
                // 後端存的是 'content'，前端 addMessage 接收文字
                // 後端存 sender: 'user' 或 'ai'，剛好對應 CSS class
                addMessage(msg.content, msg.sender);
            });
        }
    } catch (err) {
        console.error("Failed to load history:", err);
    }
}

// ... (aiReply, sendMessage 及其餘事件監聽保持不變) ...
async function aiReply(userText) {
  if (!currentUser) {
      addMessage("❌ 請先登入才能使用聊天功能", "ai");
      return;
  }

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