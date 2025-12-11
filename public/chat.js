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
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: userText })
    });

    // 如果伺服器回傳錯誤 (例如 500)，嘗試讀取錯誤訊息
    if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        // 優先顯示後端回傳的 error 欄位，如果沒有則顯示狀態碼
        throw new Error(errorData.error || `Server Error: ${res.status}`);
    }

    const data = await res.json();
    const reply = data.message?.content || "AI 沒回應";
    addMessage(reply, "ai");

  } catch (err) {
    console.error(err);
    // 這裡會將真實的錯誤原因顯示在聊天視窗中，方便除錯
    addMessage(`❌ 發生錯誤：${err.message}`, "ai");
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