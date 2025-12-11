import express from "express";
import cors from "cors";
import { GoogleGenerativeAI } from "@google/generative-ai";
import path from "path";
import { fileURLToPath } from "url";

// ESM 取得 __dirname
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();

// 中間件
app.use(cors());
app.use(express.json());

// 設定靜態資源目錄 (檔案現在應該在 public 資料夾內)
app.use(express.static(path.join(__dirname, "public")));

// 初始化 Gemini API (從環境變數讀取 Key)
// 注意：如果沒有設定 Key，這裡會報錯，請確保在 Vercel 後台設定
const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);

// 聊天 API
app.post("/chat", async (req, res) => {
  const userMessage = req.body.message;

  if (!process.env.GEMINI_API_KEY) {
    return res.status(500).json({ error: "Server 尚未設定 GEMINI_API_KEY" });
  }

  try {
    // 使用 Gemini 1.5 Flash 模型 (速度快且成本低/免費額度高)
    const model = genAI.getGenerativeModel({ model: "gemini-1.5-flash" });

    // 發送訊息給模型
    const result = await model.generateContent(userMessage);
    const response = await result.response;
    const text = response.text();

    // 回傳給前端
    res.json({ message: { content: text } });

  } catch (err) {
    console.error("Gemini API Error:", err);
    res.status(500).json({ error: "AI 回應失敗，請稍後再試" });
  }
});

// 首頁路由
app.get("/", (req, res) => {
  res.sendFile(path.join(__dirname, "public", "index.html"));
});

// 啟動 Server (本地開發用)
// Vercel 會自動處理 export default app，但這段讓你在本地也能跑
if (process.env.NODE_ENV !== "production") {
    const PORT = process.env.PORT || 3000;
    app.listen(PORT, () => console.log(`Server running on http://localhost:${PORT}`));
}

// 為了讓 Vercel 正確識別 Express app，必須導出 app
export default app;