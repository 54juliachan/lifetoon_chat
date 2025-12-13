import os
import json
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, auth

app = FastAPI()

# --- 初始化 Firebase Admin ---
# 注意：在 Vercel 上，我們通常將 Service Account JSON 的內容壓縮成一行字串，
# 放在環境變數 FIREBASE_SERVICE_ACCOUNT_JSON 中。
if not firebase_admin._apps:
    service_account_info = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
    if service_account_info:
        cred = credentials.Certificate(json.loads(service_account_info))
        firebase_admin.initialize_app(cred)
    else:
        print("Warning: FIREBASE_SERVICE_ACCOUNT_JSON not set. Auth verification may fail.")

# --- 初始化 Gemini ---
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# 定義請求資料模型
class ChatRequest(BaseModel):
    message: str

@app.post("/api/chat")
async def chat(request: ChatRequest, authorization: str = Header(None)):
    # 1. 檢查 Token 是否存在
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    token = authorization.split("Bearer ")[1]

    try:
        # 2. 驗證 Firebase Token
        #這會確認 Token 是否由 Firebase 簽發且未過期
        decoded_token = auth.verify_id_token(token)
        # 你也可以在這裡取得使用者資訊，例如 uid = decoded_token['uid']
        
    except Exception as e:
        print(f"Token verification failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    # 3. 呼叫 Gemini API
    try:
        model = genai.GenerativeModel("gemini-1.5-flash") # 或 gemini-2.0-flash
        response = model.generate_content(request.message)
        return {"message": {"content": response.text}}
        
    except Exception as e:
        print(f"Gemini API Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))