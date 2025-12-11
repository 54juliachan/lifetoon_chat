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
  if (title) { // 加上判斷避免報錯
      title.textContent = getTodayDate();
  }
});


const input = document.getElementById("userInput");
const btn = document.getElementById("sendBtn");
const messages = document.getElementById("chatMessages");

// 送出訊息事件
if (btn) { // 加上判斷避免報錯
    btn.addEventListener("click", sendMessage);
}
if (input) { // 加上判斷避免報錯
    input.addEventListener("keypress", (e) => {
      if (e.key === "Enter") sendMessage();
    });
}

// 插入訊息泡泡
function addMessage(text, sender) {
  if (!messages) return; // 安全檢查
  const bubble = document.createElement("div");
  bubble.classList.add("message", sender);
  bubble.textContent = text;

  messages.appendChild(bubble);
  messages.scrollTop = messages.scrollHeight;
}

// 呼叫後端 API 獲取 AI 回覆
async function aiReply(userText) {
  try {
    // ❌ 錯誤寫法 (舊的)： const res = await fetch("http://localhost:3000/chat", ...
    // ✅ 正確寫法：使用相對路徑 "/chat"
    // 這樣無論是在 localhost 還是 Vercel，它都會自動連到當前的伺服器
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: userText })
    });

    if (!res.ok) {
        throw new Error(`Server error: ${res.status}`);
    }

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