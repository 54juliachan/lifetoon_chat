import express from "express";
import cors from "cors";
import ollama from "ollama";  // 官方套件

const app = express();
app.use(cors());
app.use(express.json());

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

app.listen(3000, () => console.log("Server running on http://localhost:3000"));
