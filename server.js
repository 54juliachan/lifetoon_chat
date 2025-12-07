import express from "express";
import cors from "cors";
import ollama from "ollama"; // 官方套件
import path from "path";
import { fileURLToPath } from "url";

// ESM 取得 __dirname
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();

// 中間件
app.use(cors());
app.use(express.json());

// 靜態資源目錄（放前端檔案：index.html、style.css、script.js）
app.use(express.static(path.join(__dirname, "public")));

// 聊天 API
app.post("/chat", async (req, res) => {
  const userMessage = req.body.message;

  try {
    // 使用 Ollama 官方套件呼叫本地模型
    const response = await ollama.chat({
      model: "gemma3",   // 改成你已 pull 的模型
      messages: [{ role: "user", content: userMessage }],
    });

    // 回傳給前端
    res.json({ message: { content: response.message.content } });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "伺服器錯誤" });
  }
});

// 首頁路由（打開 / 時會看到 index.html）
app.get("/", (req, res) => {
  res.sendFile(path.join(__dirname, "public", "index.html"));
});

// 啟動 Server
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`Server running on http://localhost:${PORT}`));
