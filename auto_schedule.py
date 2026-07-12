import os
import requests
import ddddocr
from bs4 import BeautifulSoup
import time
import datetime

# ====== 配置区域 ======
USER = os.environ.get("EDU_USER", "212404657")
PWD = os.environ.get("EDU_PWD", "lc010913.")
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN", "f64d5b2610eb492b8f0033cfc74b87c3")
# ======================

def login():
    base_url = "https://jwc.fdzcxy.edu.cn/"
    captcha_url = base_url + "ValidateCookie.asp"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0",
        "Referer": base_url
    }

    ocr = ddddocr.DdddOcr(beta=True, show_ad=False)
    print("[*] 开始全自动突破验证码登录...")
    
    max_retries = 100
    for attempt in range(max_retries):
        session = requests.Session()
        session.headers.update(headers) 
        
        res_main = session.get(base_url, timeout=10)
        res_main.encoding = 'gb2312'
        
        soup_main = BeautifulSoup(res_main.text, 'html.parser')
        form = soup_main.find('form', id='frm')
        login_url = base_url + (form.get('action') if form and form.get('action') else "loginchk.asp")
            
        res_captcha = session.get(captcha_url + "?id=" + str(time.time()), timeout=10)
        if res_captcha.status_code != 200:
            continue
            
        captcha_text = ocr.classification(res_captcha.content)
        
        if len(captcha_text) != 4 or not captcha_text.isalnum():
            print(f"[*] 尝试 {attempt + 1}/{max_retries}: 识别为 '{captcha_text}' (跳过)")
            time.sleep(0.3)
            continue
            
        print(f"[*] 尝试 {attempt + 1}/{max_retries}: 识别为 '{captcha_text}' (发起登录)")
        data = {
            "muser": USER,
            "passwd": PWD,
            "code": captcha_text
        }
        
        res_login = session.post(login_url, data=data, allow_redirects=False, timeout=10)
        
        login_html = ""
        if res_login.status_code == 200:
            res_login.encoding = 'gb2312'
            login_html = res_login.text
            
        if "验证码不正确" in login_html or "验证码" in login_html or "输入错误" in login_html:
            time.sleep(0.3)
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

    print(f"[-] 连续 {max_retries} 次尝试均失败。")
    return None

def fetch_and_parse_schedule(session):
    print("\n[*] 登录成功，开始拉取课表数据...")
    
    schedule_url = "https://jwc.fdzcxy.edu.cn/kb/zkb_xs.asp"
    print(f"[*] 正在获取课表: {schedule_url}")
    
    res_schedule = session.get(schedule_url, timeout=15)
    res_schedule.encoding = 'gb2312'
    
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
            
        # 1. 提取时间
        time_parts = tds[0].get_text(separator='|', strip=True).split('|')
        jie_num = time_parts[0] if len(time_parts) >= 1 else str(i)
        time_val = time_parts[1] if len(time_parts) >= 2 else f"第{jie_num}节"
            
        cell_text = tds[col_idx].get_text(separator=' ', strip=True)
        if cell_text and cell_text != '' and cell_text != '&nbsp;':
            # 2. 提取课程和地点
            parts = cell_text.split()
            course_name = parts[0][:10] if len(parts) > 0 else "未知课程"
            
            # 通常教务系统的课表，第二段文本大概率是地点或教室
            location = parts[1][:10] if len(parts) > 1 else ""
            
            # 拼接短标题 (用于微信气泡外显): "08:00 高数 A101"
            short_item = f"{time_val} {course_name} {location}".strip()
            short_classes.append(short_item)
            
            # 拼接详情内容
            classes.append(f"⏰ {time_val}\n📚 {course_name}\n📍 {location}".strip())
            
    if not classes:
        full_msg = f"明天是{tomorrow_zh}，您全天没课，可以自由安排！"
        short_title = "明日无课，安心休息"
    else:
        full_msg = f"📅 【{tomorrow_zh} 课表】\n\n" + "\n\n".join(classes)
        # 直接拿空格拼接，不再带"明:"前缀
        short_title = " ".join(short_classes)
        
        # 微信外显字数限制防截断
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
        res = requests.post(url, json=data, timeout=10)
        if res.status_code == 200 and res.json().get('code') == 200:
            print("[+] 微信推送成功！")
        else:
            print("[-] 微信推送失败:", res.text)
    except Exception as e:
        print("[-] 微信推送请求异常:", e)

if __name__ == "__main__":
    session = login()
    if session:
        short_title, schedule_msg = fetch_and_parse_schedule(session)
        push_to_wechat(short_title, schedule_msg)
