// public/home.js
document.addEventListener("DOMContentLoaded", () => {
  // 取得 HTML 中的 input 與 button 元素
  const homeInput = document.querySelector(".system-input input");
  const homeBtn = document.getElementById("sendBtn");

  // 導向聊天室的邏輯
  function redirectToChat() {
    const message = homeInput.value.trim();
    if (message) {
      // 將訊息暫存在 localStorage，讓 chat.html 可以讀取
      localStorage.setItem("pendingMessage", message);
      // 跳轉頁面
      window.location.href = "chat.html";
    }
  }

  // 點擊按鈕觸發
  if (homeBtn) {
    homeBtn.addEventListener("click", redirectToChat);
  }

  // 按下 Enter 鍵觸發
  if (homeInput) {
    homeInput.addEventListener("keypress", (e) => {
      if (e.key === "Enter") redirectToChat();
    });
  }
});