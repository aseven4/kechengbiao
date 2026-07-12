import os
import requests
import ddddocr
from bs4 import BeautifulSoup
import time
import datetime
import random

# ====== 配置区域 ======
USER = os.environ.get("EDU_USER", "212404657")
PWD = os.environ.get("EDU_PWD", "lc010913.")
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN", "f64d5b2610eb492b8f0033cfc74b87c3")
# ======================

def check_holiday(bj_now):
    """
    检查是否是寒暑假。如果是，直接返回 True 阻止程序继续运行。
    规则：1月15日到2月底，以及7月1日到8月底视为假期。
    """
    month = bj_now.month
    day = bj_now.day
    
    if month == 7 or month == 8:
        return True
    if month == 1 and day >= 15:
        return True
    if month == 2:
        return True
    return False

def login():
    base_url = "https://jwc.fdzcxy.edu.cn/"
    captcha_url = base_url + "ValidateCookie.asp"
    
    # 3. 随机浏览器标识池（防封锁机制）
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15"
    ]
    
    ocr = ddddocr.DdddOcr(beta=True, show_ad=False)
    print("[*] 开始全自动突破验证码登录...")
    
    max_retries = 100
    for attempt in range(max_retries):
        try:
            session = requests.Session()
            # 每次请求随机挑选一个 User-Agent
            headers = {
                "User-Agent": random.choice(user_agents),
                "Referer": base_url
            }
            session.headers.update(headers) 
            
            res_main = session.get(base_url, timeout=15)
            res_main.encoding = 'gb2312'
            
            soup_main = BeautifulSoup(res_main.text, 'html.parser')
            form = soup_main.find('form', id='frm')
            login_url = base_url + (form.get('action') if form and form.get('action') else "loginchk.asp")
                
            res_captcha = session.get(captcha_url + "?id=" + str(time.time()), timeout=15)
            if res_captcha.status_code != 200:
                continue
                
            captcha_text = ocr.classification(res_captcha.content)
            
            if len(captcha_text) != 4 or not captcha_text.isalnum():
                print(f"[*] 尝试 {attempt + 1}/{max_retries}: 识别为 '{captcha_text}' (跳过)")
                # 3. 随机休眠 0.5 到 1.5 秒，模拟真人慢速操作
                time.sleep(random.uniform(0.5, 1.5))
                continue
                
            print(f"[*] 尝试 {attempt + 1}/{max_retries}: 识别为 '{captcha_text}' (发起登录)")
            data = {
                "muser": USER,
                "passwd": PWD,
                "code": captcha_text
            }
            
            res_login = session.post(login_url, data=data, allow_redirects=False, timeout=15)
            
            login_html = ""
            if res_login.status_code == 200:
                res_login.encoding = 'gb2312'
                login_html = res_login.text
                
            if "验证码不正确" in login_html or "验证码" in login_html or "输入错误" in login_html:
                time.sleep(random.uniform(1.0, 2.5))
                continue
            elif "密码错误" in login_html or "不存在" in login_html:
                print("[-] 账号或密码错误，请检查！")
                return None
            
            if res_login.status_code == 302 and 'main.asp' in res_login.headers.get('Location', ''):
                print(f"\n[+] 突破成功！共尝试 {attempt + 1} 次。")
                return session
                
            if not login_html:
                print(f"\n[+] 突破成功！共尝试 {attempt + 1} 次。")
                return session

        except Exception as e:
            print(f"[*] 尝试 {attempt + 1}/{max_retries}: 网络波动或超时，休息后重试...")
            time.sleep(random.uniform(2.0, 4.0))
            continue

    print(f"[-] 连续 {max_retries} 次尝试均失败。")
    return None

def fetch_and_parse_schedule(session):
    print("\n[*] 登录成功，开始拉取课表数据...")
    
    # 恢复为默认的课表地址（抓取本周）
    schedule_url = "https://jwc.fdzcxy.edu.cn/kb/zkb_xs.asp"
    print(f"[*] 正在获取课表: {schedule_url}")
    
    # 2. 课表拉取的重试机制 (最多试3次)
    res_schedule = None
    for fetch_attempt in range(3):
        try:
            res_schedule = session.get(schedule_url, timeout=20)
            res_schedule.encoding = 'utf-8'
            break
        except Exception as e:
            print(f"[-] 获取课表时网络超时 (尝试 {fetch_attempt+1}/3): {e}")
            if fetch_attempt == 2:
                return "⚠️课表获取超时", "教务系统网络太卡啦，获取课表失败，请手动登录查看！"
            time.sleep(3)
            
    soup = BeautifulSoup(res_schedule.text, 'html.parser')
    
    table = soup.find('table', class_='table1')
    if not table:
        print("[-] 未能在页面中找到课表对应的表格(class=table1)")
        return "课表获取失败", "未能找到课表表格，请联系助手更新。"
        
    print("[+] 成功解析出课表框架，正在提取明天的课程...")
    
    utc_now = datetime.datetime.utcnow()
    bj_now = utc_now + datetime.timedelta(hours=8)
    tomorrow = bj_now + datetime.timedelta(days=1)
    tomorrow_weekday = tomorrow.weekday()
    
    weekdays_zh = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    tomorrow_zh = weekdays_zh[tomorrow_weekday]
    
    if tomorrow_weekday >= 5: 
        msg = f"明天是{tomorrow_zh}，好好休息吧，没有课哦！\n\n(注: 周末如有临时安排请留意通知)"
        return "明日无课，安心休息", msg
        
    col_idx = tomorrow_weekday + 1 
    
    classes = []
    short_classes = [] 
    
    for i in range(1, 12):
        row_id = f"tr{i}"
        tr = table.find('tr', id=row_id)
        if not tr: continue
            
        tds = tr.find_all('td')
        if len(tds) < 6: continue
            
        time_parts = tds[0].get_text(separator='|', strip=True).split('|')
        jie_num = time_parts[0] if len(time_parts) >= 1 else str(i)
        time_val = time_parts[1] if len(time_parts) >= 2 else f"第{jie_num}节"
            
        cell_text = tds[col_idx].get_text(separator=' ', strip=True)
        if cell_text and cell_text != '' and cell_text != '&nbsp;':
            parts = cell_text.split()
            course_name = parts[0] if len(parts) > 0 else "未知课程"
            location = parts[1] if len(parts) > 1 else ""
            
            short_item = f"{time_val} {course_name[:12]} {location}".strip()
            short_classes.append(short_item)
            
            classes.append(f"⏰ {time_val}\n📚 {course_name}\n📍 {location}".strip())
            
    if not classes:
        full_msg = f"明天是{tomorrow_zh}，您全天没课，可以自由安排！"
        short_title = "明日无课，安心休息"
    else:
        full_msg = f"📅 【{tomorrow_zh} 课表】\n\n" + "\n\n".join(classes)
        short_title = " ".join(short_classes)
        
        if len(short_title) > 65: 
            short_title = short_title[:62] + "..."
            
    print("[+] 明日课表文字生成完毕！")
    return short_title, full_msg

def push_to_wechat(title, text_content):
    if not text_content:
        return
    if "在此处填写" in PUSHPLUS_TOKEN:
        print("[-] 未配置 PushPlus Token，跳过微信推送。")
        return
        
    print("[*] 正在将课表推送到微信...")
    url = "http://www.pushplus.plus/send"
    data = {
        "token": PUSHPLUS_TOKEN,
        "title": title,
        "content": text_content,
        "template": "txt" 
    }
    
    try:
        res = requests.post(url, json=data, timeout=15)
        if res.status_code == 200 and res.json().get('code') == 200:
            print("[+] 微信推送成功！")
        else:
            print("[-] 微信推送失败:", res.text)
    except Exception as e:
        print("[-] 微信推送请求异常:", e)

if __name__ == "__main__":
    utc_now = datetime.datetime.utcnow()
    bj_now = utc_now + datetime.timedelta(hours=8)
    
    # 4. 节假日智能跳过 (已开启)
    if check_holiday(bj_now):
        print("[*] 当前处于寒暑假期间，智能休眠，不进行推送。")
        import sys; sys.exit(0)
        
    session = login()
    if session:
        short_title, schedule_msg = fetch_and_parse_schedule(session)
        push_to_wechat(short_title, schedule_msg)
    else:
        # 1. 失败告警机制
        push_to_wechat("⚠️教务系统登录失败", "重试了100次都没进去，可能是系统维护或密码修改了，请注意手动核查明日课表！")
