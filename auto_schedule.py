import os
import requests
import ddddocr
from bs4 import BeautifulSoup
import time
import datetime
import random
import re
from icalendar import Calendar, Event
import pytz

USER = os.environ.get("EDU_USER", "212404657")
PWD = os.environ.get("EDU_PWD", "lc010913.")
TZ = pytz.timezone('Asia/Shanghai')

def login():
    base_url = "https://jwc.fdzcxy.edu.cn/"
    captcha_url = base_url + "ValidateCookie.asp"
    
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
                time.sleep(random.uniform(0.5, 1.5))
                continue
                
            print(f"[*] 尝试 {attempt + 1}/{max_retries}: 识别为 '{captcha_text}'")
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
            time.sleep(random.uniform(2.0, 4.0))
            continue

    print(f"[-] 连续 {max_retries} 次尝试均失败。")
    return None

def fetch_schedule(session):
    print("\n[*] 登录成功，开始拉取本周课表数据...")
    schedule_url = "https://jwc.fdzcxy.edu.cn/kb/zkb_xs.asp"
    
    res_schedule = None
    for fetch_attempt in range(3):
        try:
            res_schedule = session.get(schedule_url, timeout=20)
            res_schedule.encoding = 'utf-8'
            break
        except Exception as e:
            print(f"[-] 获取课表时网络超时 (尝试 {fetch_attempt+1}/3): {e}")
            time.sleep(3)
            
    if not res_schedule:
        print("[-] 拉取课表失败。")
        return None
        
    soup = BeautifulSoup(res_schedule.text, 'html.parser')
    table = soup.find('table', class_='table1')
    if not table:
        print("[-] 未能在页面中找到课表对应的表格(class=table1)")
        return None
        
    return soup, table

def parse_time(time_str):
    try:
        h, m = map(int, time_str.split(':'))
        return datetime.time(h, m)
    except:
        return datetime.time(8, 0) # 默认

def update_calendar(soup, table):
    text = soup.get_text()
    match = re.search(r'\((\d{4}/\d{1,2}/\d{1,2})-\d{4}/\d{1,2}/\d{1,2}\)', text)
    
    if match:
        monday_str = match.group(1)
        monday_date = datetime.datetime.strptime(monday_str, "%Y/%m/%d").date()
    else:
        print("[-] 未能从页面提取本周日期，默认使用当前周一。")
        today = datetime.date.today()
        monday_date = today - datetime.timedelta(days=today.weekday())
        
    print(f"[*] 解析到本周一日期: {monday_date}")
    
    parsed_events = []
    classes_per_day = {i: 0 for i in range(7)}
    
    # 遍历1-7天（列，2到8列，如果第一列是节次）
    for day_offset in range(7):
        current_date = monday_date + datetime.timedelta(days=day_offset)
        col_idx = day_offset + 1
        
        for i in range(1, 12):
            row_id = f"tr{i}"
            tr = table.find('tr', id=row_id)
            if not tr: continue
                
            tds = tr.find_all('td')
            if len(tds) < 6 or col_idx >= len(tds): continue
                
            time_parts = tds[0].get_text(separator='|', strip=True).split('|')
            jie_num = time_parts[0] if len(time_parts) >= 1 else str(i)
            time_val = time_parts[1] if len(time_parts) >= 2 else f"08:00"
                
            cell_text = tds[col_idx].get_text(separator=' ', strip=True)
            if cell_text and cell_text != '' and cell_text != '&nbsp;':
                parts = cell_text.split()
                course_name = parts[0] if len(parts) > 0 else "未知课程"
                location = parts[1] if len(parts) > 1 else ""
                
                start_time = parse_time(time_val)
                start_dt = datetime.datetime.combine(current_date, start_time)
                start_dt = TZ.localize(start_dt)
                
                # 每节课45分钟，中间休息10分钟，两节连上共100分钟
                end_dt = start_dt + datetime.timedelta(minutes=100)
                
                uid = f"{current_date.strftime('%Y%m%d')}-{jie_num}-{course_name}@fdzcxy"
                
                parsed_events.append({
                    "uid": uid,
                    "summary": course_name,
                    "location": location,
                    "start_dt": start_dt,
                    "end_dt": end_dt
                })
                classes_per_day[day_offset] += 1
                
        # 每天遍历完后，如果今天一节课都没有，就加一个全天“今日无课”的占位符
        if classes_per_day[day_offset] == 0:
            parsed_events.append({
                "uid": f"no-class-{current_date.strftime('%Y%m%d')}@fdzcxy",
                "summary": "今日无课",
                "location": "",
                "start_dt": current_date # 传入 date 对象表示全天事件
            })

    cal_file = "schedule.ics"
    cal = Calendar()
    cal.add('prodid', '-//Auto Schedule Sync//fdzcxy//CN')
    cal.add('version', '2.0')
    
    if os.path.exists(cal_file):
        try:
            with open(cal_file, 'rb') as f:
                old_cal = Calendar.from_ical(f.read())
            
            week_start = monday_date
            week_end = monday_date + datetime.timedelta(days=6)
            
            for component in old_cal.walk():
                if component.name == "VEVENT":
                    dtstart = component.get('dtstart').dt
                    if isinstance(dtstart, datetime.datetime):
                        dt_date = dtstart.date()
                    else:
                        dt_date = dtstart
                    
                    if not (week_start <= dt_date <= week_end):
                        cal.add_component(component)
        except Exception as e:
            print(f"[-] 读取旧日历出错: {e}，将重新创建。")
            
    for ev_data in parsed_events:
        event = Event()
        event.add('uid', ev_data["uid"])
        event.add('summary', ev_data["summary"])
        if ev_data.get("location"):
            event.add('location', ev_data["location"])
        event.add('dtstart', ev_data["start_dt"])
        if "end_dt" in ev_data:
            event.add('dtend', ev_data["end_dt"])
        event.add('dtstamp', datetime.datetime.now(TZ))
        cal.add_component(event)
        
    with open(cal_file, 'wb') as f:
        f.write(cal.to_ical())
        
    print(f"[+] 日历更新完成！")

if __name__ == "__main__":
    session = login()
    if session:
        result = fetch_schedule(session)
        if result:
            soup, table = result
            update_calendar(soup, table)
    else:
        print("[-] 登录失败，退出。")
