#cài thư viện cần thiết
# pip install discord.py aiohttp python-dotenv`

import discord
import aiohttp
import asyncio
import os
import re
import json
from dotenv import load_dotenv
load_dotenv()

# ====== KEY VÀ TOKEN ======
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SERPER_API_KEY = os.getenv("SERPER_API_KEY")

# ====== ID CỦA KÊNH QUIZ VÀ BOT ======
QUIZ_CHANNEL_CHOICES = {
    "1": 1257978256435712030,  # Quiz Global 1257978256435712030
    "2": 1158978885581557780,  # Quiz VN
}
QUIZ_BOT_CHOICES = {
    "1": 558996910581612545,  # Bot Aethir
    "2": 1335691906335772804, # Bot vn
} 
QUIZ_CHANNEL_ID = None #Quiz_aethir 1257978256435712030
QUIZ_BOT_ID = None #botQuiz_aethir 558996910581612545

# ====== KHỞI TẠO BOT ======

client = discord.Client()
@client.event
async def on_ready():
    global QUIZ_CHANNEL_ID, QUIZ_BOT_ID
    print(f"Đăng nhập thành công: {client.user} (ID: {client.user.id})")
    QUIZ_CHANNEL_ID = choose_quiz_channel_id()
    QUIZ_BOT_ID = choose_quiz_bot_id()
    print("<==== SS ====>")
    print(f"Kênh = {QUIZ_CHANNEL_ID}")
    print(f"Bot = {QUIZ_BOT_ID}")
    print("**** Let's go ****")
    
@client.event
async def on_message(message): # Lắng nghe msg từ discord và lọc lấy msg cần dùng.
    print(f"Start listening messages in channel")
    if message.channel.id == QUIZ_CHANNEL_ID:
        if message.author.id == QUIZ_BOT_ID or message.author.bot:
            if message.content:
                if is_quiz_message(message.content, "Contents"):
                    await handle_quiz(message)
            if message.embeds:
                for embed in message.embeds:
                    if is_quiz_message(embed.title, "Embeds"):
                        await handle_quiz(embed.title, embed.description)
            
                

# ====== XÂY DỰNG ======
#Chọn kênh cụ thể để nghe msg
def choose_quiz_channel_id(): 
    print("Chọn kênh quiz:")
    print("1. Quizz Aethir Games")
    print("2. Quiz VN Local")
    print("3. Nhập ID thủ công")
    
    choice = input("Nhập lựa chọn (1/2/3): ").strip()

    if choice in QUIZ_CHANNEL_CHOICES:
        return QUIZ_CHANNEL_CHOICES[choice]
    elif choice == "3":
        try:
            user_input = int(input("Nhập Channel ID: ").strip())
            return user_input
        except ValueError:
            print("❌ ID không hợp lệ, dùng mặc định 1.")
            return QUIZ_CHANNEL_CHOICES["1"]
    else:
        print("❌ Lựa chọn không hợp lệ, Channel = Test")
        return 1401580731225866312

#Chọn Bot gửi msg        
def choose_quiz_bot_id(): 
    print("Chọn bot quiz:")
    print("1. Bot Aethir")
    print("2. Bot Vn-local")
    print("3. Nhập ID thủ công")
    print("4. Bot không xác định")
    
    choice = input("Nhập lựa chọn (1/2/3/4): ").strip()
    
    if choice in QUIZ_BOT_CHOICES:
        return QUIZ_BOT_CHOICES[choice]
    elif choice == "3":
        try:
            user_input = int(input("Nhập Bot ID: ").strip())
            return user_input
        except ValueError:
            print("❌ ID không hợp lệ, Bot = None")
            return QUIZ_BOT_CHOICES["1"]
    elif choice == "4":
        print ("Bot = None")
        return None
    else:
            print("❌ Lựa chọn không hợp lệ, Bot = Test")
            return 1161783017245773864

# Hàm chính để lấy msg và trả về kết quả
async def handle_quiz(question, description = None):
    if description:
        desc_lines = description.strip().splitlines()
        desc_final = "\n".join(desc_lines[:4])
        print(f"\n -> Quizz: \n{question}\n{description}")
        answer = await ask_gpt(question, desc_final)
        if answer:
            print(f"\n ** Đáp án: --> {answer}\n")
        else:
            print("Lỗi!")
    else:
        question = question.content.strip()
        print(f"\n -> Quizz: \n{question}\n")
        answer = await ask_gpt(question)
        if answer:
            print(f"\n ** Đáp án: --> {answer}\n")
        else:
            print("Lỗi!")
    await asyncio.sleep(1)
      
def is_quiz_message(msgText, msgFormat = None):
    if not msgText: return False
    msgText = msgText.strip()
    if msgFormat == "Embeds":
        if msgText.endswith("?"):
            return True
    elif msgFormat == "Contents":
        if re.match(r"^question\s*\d+", msgText, re.IGNORECASE) and "\n" in msgText :
            return True
    else: return False

# Hàm gửi quizz lên gpt để tìm đáp án           
async def ask_gpt(question, description = ""):
    if description:
        question_final = question
    else:
        #Tối ưu question
        question_short = re.sub(r"^Question\s+\d+\s*\n", "", question)
        question_final = question_short.strip().split("\n", 1)[0]
    #Gửi question lên serper
    search_data = await search_serper(question_final)
    if search_data:
        #Ghép dữ liệu tìm kiếm thành text
        context_parts = []
        for item in search_data.get("organic", [])[:5]:
            context_parts.append(f"{item.get('title')}\n{item.get('snippet')}\n{item.get('link')}")
        searchResults = "\n\n".join(context_parts)
        #print(f"Kết quả tìm kiếm: {searchResults}")
        #print(f"Câu hỏi: {question}\n{description}")
        try:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            }
            system_prompt = (
                "Mày là thằng trẻ trâu thông minh trả lời quiz."
                "Tìm kiếm và kiểm tra thông tin trong mục 'Thông tin tìm kiếm' tao gửi. Chú ý mapping câu hỏi và đáp án phải trùng khớp. Chỉ chọn đáp án đúng nhất trong danh sách đáp án tao đưa"
                "Chỉ output: 1 ký tự (A/B/C/D hoặc 1/2/3/4) - nội dung của đáp án, xuống dòng, rồi 1 câu cà khịa <=10 chữ."
                "Ví dụ: '1 - Éo nhớ đáp án \n Dễ vcl'. Không giải thích."
                "Nếu không tìm thấy thông tin chính xác, trả lời đáp án gần đúng nhất kèm với '- Đcm! khó vl, tao méo biết. Mớm cho mày đáp án gần đúng'."
            )
            payload = {
                "model": "gpt-4o-mini",
                "temperature": 0,
                "max_tokens": 30,
                "top_p": 1,
                "n": 1,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Câu hỏi: {question}\n{description}\n\n===== THÔNG TIN TÌM KIẾM =====\n{searchResults}\n===== HẾT THÔNG TIN ====="}
                ]
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    data = await response.json()
                    if "choices" in data:
                        answer = data["choices"][0]["message"]["content"]
                        return answer.strip()
                    else:
                        print(f"Lỗi GPT API: {data}")
                        return None
        except Exception as e:
            print(f"❌ Lỗi GPT: {e}")
            print("📩 Payload gửi GPT:", payload)
            return None

#Search nội dung question
async def search_serper(query): 
    try:
        url = "https://google.serper.dev/search"
        headers = {
            "X-API-KEY": SERPER_API_KEY,
            "Content-Type": "application/json"
        }
        payload = {"q": query, "gl": "vn", "hl": "vi"}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                status = response.status
                if status == 200:
                    return await response.json()
                else:
                    print(f"Lỗi SERPER API: {status}")
                    return None
    except Exception as e:
        print(f"❌ Lỗi SERPER: {e}")
        print("📩 Payload gửi SERPER:", payload)
        return None

client.run(DISCORD_BOT_TOKEN)
