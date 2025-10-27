import argparse
import shutil
from selenium.webdriver.common.by import By
from browser_automation import BrowserManager, Node
from utils import Utility, Chromium
import discord
import aiohttp
import asyncio
import os
import re
import threading
import queue
from dotenv import load_dotenv
load_dotenv()

# ====== KEY VÀ TOKEN ======
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SERPER_API_KEY = os.getenv("SERPER_API_KEY")

# ====== KHỞI TẠO BOT ======
client = discord.Client()
SERVER_ID = int(Utility.read_config('QUIZ_SERVER_ID')[0])
CHANNEL_ID = int(Utility.read_config('QUIZ_CHANNEL_ID')[0])
BOT_ID = int(Utility.read_config('QUIZ_BOT_ID')[0])

# ====== THIẾT LẬP TRÌNH DUYỆT ======
driverList = []
task_queue = queue.Queue()
worker_queues = []
worker_queues_lock = threading.Lock()
class Setup:
    def __init__(self, node: Node, profile) -> None:
        self.node = node
        self.profile = profile
        
    def _run(self):
        self.node.go_to(f'https://discord.com/channels/@me', method="get")
        Utility.wait_time(10)

class Auto:
    def __init__(self, node: Node, profile: dict) -> None:
        self.driver = node._driver
        self.node = node
        self.profile_name = profile.get('profile_name')
        #self.task_queue = queue.Queue()
    def is_login(self):
        user_name = self.node.get_text(By.XPATH, '//div[contains(@class, "panelTitleContainer")]')
        if user_name:
            self.node.log(f'Đã login với user: {user_name}')
            return True
        else:
            self.node.log(f'Chưa login, comfirm login')
        return False
    def task_worker(self, answer):
        '''
        Hàm này chạy BÊN TRONG thread của worker,
        chỉ xử lý cho driver của riêng nó.
        Hàm này sẽ click vào đáp án của quizz.
        :param answer: Đáp án cần click 1/2/3/4
        '''
        try:
            answer = int(answer)
            elm = self.node.find_all(By.XPATH, '//button[contains(@class,"colorBrand__201d5 sizeSmall__201d5")]')
            if elm and len(elm) >= answer:
                elm[answer - 1].click()
                self.node.log(f"Đã click vào đáp án: {answer}")
        except Exception as e:
            self.node.log(f"Lỗi khi click vào đáp án: {e}")

    def _run(self):
        self.node.go_to(f'https://discord.com/channels/{SERVER_ID}/{CHANNEL_ID}', method="get")
        Utility.wait_time(10)
        if not self.is_login():
            self.node.log('Vui lòng đăng nhập trong 60s...')
            Utility.wait_time(60)
            if not self.is_login():
                return
        else:
            self_node = [self.driver, self.profile_name]
            driverList.append(self_node)
            return
        '''
        # Đăng ký worker cho node này
        with worker_queues_lock:
            worker_queues.append(self.task_queue)
        # Bắt đầu chờ task
        while True:
            try:
                # Chờ task (hàm này BLOCKING, thread sẽ ngủ ở đây)
                answer_task = self.task_queue.get()
                if answer_task is None:
                    self.node.log("Nhận tín hiệu dừng worker.")
                    break
                # Chạy task trong thread của worker
                self.task_worker(answer_task)
                # Đánh dấu task đã hoàn thành
                self.task_queue.task_done()
            except Exception as e:
                self.node.log(f"Lỗi nghiêm trọng trong worker loop: {e}")
                break
            '''
            




# ====== CẤU TRÚC HÀM CHÍNH ======
def click_quiz(answer):
    '''
    Hàm này sẽ click vào đáp án của quizz.
    :param answer: Đáp án cần click 1/2/3/4
    '''
    answer = int(answer)
    for driver, profile_name in driverList:
        node = Node(driver, profile_name)
        try:
            elm = node.find_all(By.XPATH, '//button[contains(@class,"colorBrand__201d5 sizeSmall__201d5")]')
            if elm and len(elm) >= answer:
                elm[answer - 1].click()
                print(f"Đã click vào đáp án: {answer}")
        except Exception as e:
            print(f"Lỗi khi click vào đáp án: {e}")

# Hàm chính để lấy msg và trả về kết quả
async def handle_quiz(author,question, description = None):
    if description:
        desc_lines = description.strip().splitlines()
        desc_final = "\n".join(desc_lines[:4])
        print(f"\n -> {author}\n{question}\n{description}")
        answer = await ask_gpt(question, desc_final)
        if answer:
            print(f"\n ** Đáp án: --> {answer}\n")
            task_to_send = answer[0]
            with worker_queues_lock:
                #for queue in worker_queues:
                task_queue.put(task_to_send)
        else:
            print("Lỗi!")
    else:
        question = question.content.strip()
        print(f"\n -> Quizz: \n{question}\n")
        answer = await ask_gpt(question)
        if answer:
            print(f"\n ** Đáp án: --> {answer}\n")
            task_to_send = answer[0]
            with worker_queues_lock:
                #for queue in worker_queues:
                task_queue.put(task_to_send)
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
    
def run_terminal(profiles: list[dict], max_concurrent_profiles: int = 4, auto: bool = False, headless: bool = False, disable_gpu: bool = False, sys_chrome: bool = False):
        '''
        Chạy giao diện dòng lệnh để người dùng chọn chế độ chạy.

        Args:
            profiles (list[dict]): Danh sách các profile trình duyệt có thể khởi chạy.
                Mỗi profile là một dictionary chứa thông tin, trong đó key 'profile' là bắt buộc. 
                Ví dụ: {'profile': 'profile_name', ...}
            max_concurrent_profiles (int, optional): Số lượng tối đa các hồ sơ có thể chạy đồng thời. Mặc định là 4.
            auto (bool, optional): True, bỏ qua lựa chọn terminal và chạy trực tiếp chức năng auto. Mặc định False.
            headless (bool, optional): True, sẽ ẩn duyệt trình khi chạy. Mặc định False.
            disable_gpu (bool, optional): True, tắt GPU, dành cho máy không có GPU vật lý. Mặc định False.
        
        Chức năng:
            - Hiển thị menu cho phép người dùng chọn một trong các chế độ:
                1. Set up: Chọn và mở lần lượt từng profile để cấu hình.
                2. Chạy auto: Tự động chạy các profile đã cấu hình.
                3. Xóa profile: Xóa profile đã tồn tại.
                0. Thoát chương trình.
            - Khi chọn Set up, người dùng có thể chọn chạy tất cả hoặc chỉ một số profile cụ thể.
            - Khi chọn Chạy auto, chương trình sẽ khởi động tự động với số lượng profile tối đa có thể chạy đồng thời.
            - Hỗ trợ quay lại menu chính hoặc thoát chương trình khi cần.

        Hoạt đông:
            - Gọi `run_stop()` nếu người dùng chọn Set up.
            - Gọi `run_multi()` nếu người dùng chọn Chạy auto.

        '''
        #self.headless = headless
        #self.disable_gpu = disable_gpu
        if not sys_chrome:
            path_chromium = Chromium().path
        is_run = True

        print("\n"+"=" * 70)
        print(f"⚙️  Bot Automation Quizz đang sử dụng:")
        print(f"   📍 Username:             {client.user}")
        print(f"   📍 Userid:               {client.user.id}")
        if path_chromium:
            print(f"   📍 Đường dẫn Chrome:     {path_chromium}")
        else:
            print(f"   📍 Chrome hệ thống")
        print(f"   📍 Đường dẫn Profiles:   {browserMgr.user_data_dir}")
        print("=" * 70+"\n")

        while is_run:
            user_data_profiles = []

            if browserMgr.user_data_dir.exists() and browserMgr.user_data_dir.is_dir():
                raw_user_data_profiles = [folder.name for folder in browserMgr.user_data_dir.iterdir() if folder.is_dir()]

                # Thêm các profile theo thứ tự trong profiles trước
                for profile in profiles:
                    profile_name = profile['profile_name']
                    if profile_name in raw_user_data_profiles:
                        user_data_profiles.append(profile_name)
                
                # Thêm các profile còn lại không có trong profiles vào cuối
                for profile_name in raw_user_data_profiles:
                    if profile_name not in user_data_profiles:
                        user_data_profiles.append(profile_name)
            
            if not auto:
                print("[A] 📋 Chọn một tùy chọn:")
                print("   1. Set up       - Mở lần lượt từng profile để cấu hình.")
                print("   2. Chạy auto    - Các profiles sau khi đã cấu hình.")
                if user_data_profiles:
                    print("   3. Xóa profile  - Xoá các profile đã tồn tại.") # đoạn này xuất hiện, nếu có tồn tại danh sách user_data_profiles ở trên
                print("   0. Thoát        - Thoát chương trình.")
                choice = input("Nhập lựa chọn: ")
            else:
                choice = '2'
                profile_list = profiles
                is_run = False

            if choice in ('1', '2', '3'):
                if not auto:
                    profile_list = profiles if choice in ('1', '2') else user_data_profiles
                    print("=" * 10)
                    if choice in ('1', '2'):
                        print(
                            f"[B] 📋 Chọn các profile muốn chạy {'Set up' if choice == '1' else 'Auto'}:")
                        print(f"❌ Không tồn tại profile trong file data.txt") if len(profile_list) == 0 else None
                    elif (choice in ('3')):
                        if not user_data_profiles:
                            continue
                        print("[B] 📋 Chọn các profile muốn xóa:")

                    print(f"   0. ALL ({len(profile_list)})") if len(profile_list) > 1 else None
                    for idx, profile in enumerate(profile_list, start=1):
                        print(f"   {idx}. {profile['profile_name'] if choice in ('1', '2') else profile}{' [✓]' if choice in ('1', '2') and profile['profile_name'] in user_data_profiles else ''}")

                    profile_choice = input(
                        "Nhập số và cách nhau bằng dấu cách (nếu chọn nhiều) hoặc bất kì để quay lại: ")
                else:
                    profile_choice = '0'

                selected_profiles = []
                choices = profile_choice.split()
                if "0" in choices:  # Chạy tất cả profiles
                    selected_profiles = profile_list
                else:
                    for ch in choices:
                        if ch.isdigit():
                            index = int(ch) - 1
                            if 0 <= index < len(profile_list):  # Kiểm tra index hợp lệ
                                selected_profiles.append(profile_list[index])
                            else:
                                print(f"⚠ Profile {ch} không hợp lệ, bỏ qua.")

                if not selected_profiles:
                    Utility.print_section('LỖI: Lựa chọn không hợp lệ. Vui lòng thử lại...', "🛑")
                    continue
                
                if choice == '1':
                    Utility.print_section("Bắt đầu cấu hình","🔄")                
                    browserMgr.run_stop(selected_profiles)
                    Utility.print_section("Kết thúc cấu hình","✅")                
                
                elif choice == '2':
                    Utility.print_section("BẮT ĐẦU CHƯƠNG TRÌNH","🔄")                
                    browserMgr.run_multi(profiles=selected_profiles,
                                   max_concurrent_profiles=max_concurrent_profiles)
                    is_run = False
                elif choice == '3':
                    profiles_to_deleted = []
                    for profile_name in selected_profiles:
                        # kiểm tra profile_name là string
                        if not isinstance(profile_name, str):
                            continue
                        profile_path = browserMgr.user_data_dir / profile_name
                        try:
                            shutil.rmtree(profile_path)
                            profiles_to_deleted.append(profile_name)
                        except Exception as e:
                            Utility.logger(message=f"❌ Lỗi khi xóa profile {profile_name}: {e}")
                    Utility.print_section(f"Đã xóa profile: {profiles_to_deleted}")
            elif choice == '0':  # Thoát chương trình
                is_run = False
                Utility.print_section("THOÁT CHƯƠNG TRÌNH","❎")
                exit()
            else:
                Utility.print_section('LỖI: Lựa chọn không hợp lệ. Vui lòng thử lại...', "🛑")
# Hàm chờ task
def quiz_worker():
    while True:
        try:
            answer_task = task_queue.get()
            if answer_task is None:
                print("Nhận tín hiệu dừng worker.")
                break
            click_quiz(answer_task)
            task_queue.task_done()
        except Exception as e:
            print(f"Lỗi nghiêm trọng trong worker loop: {e}")
            break


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--auto', action='store_true', help="Chạy ở chế độ tự động")
    parser.add_argument('--headless', action='store_true', help="Chạy trình duyệt ẩn")
    parser.add_argument('--disable-gpu', action='store_true', help="Tắt GPU")
    args = parser.parse_args()

    profiles = Utility.read_data('profile_name')
    max_profiles = Utility.read_config('MAX_PROFLIES')
    max_profiles = int(max_profiles[0]) if max_profiles else 4
    
    if not profiles:
        print("Không có dữ liệu để chạy")
        exit()

    browserMgr = BrowserManager(AutoHandlerClass=Auto, SetupHandlerClass=Setup)


    setup_complete_event = asyncio.Event()

    def run_terminal_wrapper(loop, event, **args):
        """
        Hàm này chạy trong thread phụ, bọc lấy run_terminal
        để gửi tín hiệu khi nó thực thi xong.
        """
        try:
            # Gọi hàm blocking run_terminal của bạn
            run_terminal(**args)
        except Exception as e:
            print(f"❌ Lỗi nghiêm trọng trong thread run_terminal: {e}")
        finally:
            # Dù thành công hay thất bại, báo cho main thread biết là đã xong
            Utility.print_section("Bắt đầu quiz","✅")                
            # Dùng call_soon_threadsafe để set Event của asyncio từ một thread khác
            loop.call_soon_threadsafe(event.set)
            quiz_worker()  # Bắt đầu worker chờ task

    @client.event
    async def on_ready():
        Utility.print_section(f"ready","✅")
        # Chạy terminal trong một luồng riêng
        ev_loop = asyncio.get_event_loop()
        terminal_args = {
            "profiles": profiles,
            "max_concurrent_profiles": max_profiles,
            "auto": args.auto,
            "headless": args.headless,
            "disable_gpu": args.disable_gpu,
            #"sys_chrome": args.sys_chrome
        }
        await asyncio.to_thread(
            run_terminal_wrapper,
            ev_loop,
            setup_complete_event,
            **terminal_args
            )

    @client.event
    async def on_message(message): # Lắng nghe msg từ discord và lọc lấy msg cần dùng.
        await setup_complete_event.wait()  # Chờ đến khi setup hoàn tất
        print(f"Start listening messages in channel")
        if message.channel.id == CHANNEL_ID:
            print(f"Message from channel matched: {message.channel.id}")
            if message.author.id == BOT_ID or message.author.bot:
                print(f"Message from bot matched: {message.author.id}")
                if message.content:
                    if is_quiz_message(message.content, "Contents"):
                        await handle_quiz(message)
                if message.embeds:
                    for embed in message.embeds:
                        if is_quiz_message(embed.title, "Embeds"):
                            await handle_quiz(embed.author, embed.title, embed.description)
    client.run(DISCORD_BOT_TOKEN)