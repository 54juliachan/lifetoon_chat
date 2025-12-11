// 取得今天日期，格式 YYYY-MM-DD
function getTodayDate() {
  const today = new Date();
  const year = today.getFullYear();
  const month = (today.getMonth() + 1).toString().padStart(2, "0");
  const day = today.getDate().toString().padStart(2, "0");
  return `${year}-${month}-${day}`;
}

// 在頁面載入時更新標題
window.addEventListener("DOMContentLoaded", () => {
  const title = document.getElementById("chatTitle");
  title.textContent = getTodayDate();
});


const input = document.getElementById("userInput");
const btn = document.getElementById("sendBtn");
const messages = document.getElementById("chatMessages");

// 送出訊息事件
btn.addEventListener("click", sendMessage);
input.addEventListener("keypress", (e) => {
  if (e.key === "Enter") sendMessage();
});

// 插入訊息泡泡
function addMessage(text, sender) {
  const bubble = document.createElement("div");
  bubble.classList.add("message", sender);
  bubble.textContent = text;

  messages.appendChild(bubble);
  messages.scrollTop = messages.scrollHeight;
}

// 呼叫後端 API 獲取 AI 回覆
async function aiReply(userText) {
  try {
    const res = await fetch("http://localhost:3000/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: userText })
    });

    const data = await res.json();
    // 取 AI 回覆
    const reply = data.message?.content || "AI 沒回應";
    addMessage(reply, "ai");
  } catch (err) {
    console.error(err);
    addMessage("連線失敗，請稍後再試", "ai");
  }
}

// 送出訊息
function sendMessage() {
  const text = input.value.trim();
  if (!text) return;

  addMessage(text, "user");
  input.value = "";

  // 呼叫真實 AI
  aiReply(text);
}

