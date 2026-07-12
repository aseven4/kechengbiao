import requests
import ddddocr
from bs4 import BeautifulSoup
import time
import cv2
import numpy as np

import os

# ====== 配置区域 ======
# 为了在云端运行的安全，我们优先从环境变量读取密码，如果不填则使用这里的默认值
USER = os.environ.get("EDU_USER", "212404657")
PWD = os.environ.get("EDU_PWD", "lc010913.")
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN", "f64d5b2610eb492b8f0033cfc74b87c3")
# ======================

def process_captcha(image_bytes):
    """
    使用 OpenCV 处理验证码图片，去除噪点和干扰线，提高 ddddocr 识别率
    """
    # 将字节转换为 numpy 数组
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    # 转灰度图
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 二值化（根据实际验证码颜色可以调整阈值，这里假设干扰线较浅）
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
    
    # 形态学操作去噪（开运算去除小噪点）
    kernel = np.ones((2, 2), np.uint8)
    opening = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
    
    # 将处理后的图像转换回字节
    _, buffer = cv2.imencode('.jpg', opening)
    return buffer.tobytes()

def login():
    base_url = "https://jwc.fdzcxy.edu.cn/"
    captcha_url = base_url + "ValidateCookie.asp"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": base_url
    }

    ocr = ddddocr.DdddOcr(show_ad=False)
    
    print("[*] 开始全自动突破验证码登录...")
    
    # 无限重试，直到登录成功（验证码识别正确）
    attempt = 1
    while True:
        print(f"\r[*] 正在进行第 {attempt} 次尝试...", end="", flush=True)
        session = requests.Session()
        res_main = session.get(base_url, headers=headers)
        res_main.encoding = 'gb2312'
        
        soup_main = BeautifulSoup(res_main.text, 'html.parser')
        form = soup_main.find('form', id='frm')
        login_url = base_url + (form.get('action') if form and form.get('action') else "loginchk.asp")
            
        res_captcha = session.get(captcha_url + "?id=" + str(time.time()), headers=headers)
        if res_captcha.status_code != 200:
            attempt += 1
            continue
            
        # 验证码预处理并识别
        processed_img = process_captcha(res_captcha.content)
        captcha_text = ocr.classification(processed_img)
        
        if len(captcha_text) < 4:
            attempt += 1
            continue
            
        data = {
            "muser": USER,
            "passwd": PWD,
            "code": captcha_text
        }
        
        res_login = session.post(login_url, data=data, headers=headers, allow_redirects=False)
        
        # 成功标志：302 跳转到 main.asp
        if res_login.status_code == 302 and 'main.asp' in res_login.headers.get('Location', ''):
            print(f"\n[+] 突破成功！共尝试 {attempt} 次。验证码识别为: {captcha_text}")
            return session
            
        attempt += 1

def fetch_and_parse_schedule(session):
    print("\n[*] 登录成功，开始拉取课表数据...")
    
    # 既然我们已经知道课表的地址了，就直接访问它
    schedule_url = "https://jwc.fdzcxy.edu.cn/zkb_xs.asp"
    print(f"[*] 正在获取课表: {schedule_url}")
    res_schedule = session.get(schedule_url)
    res_schedule.encoding = 'gb2312'
    
    soup = BeautifulSoup(res_schedule.text, 'html.parser')
    
    # 提取表头信息（学期、周次）
    title_element = soup.find('td', class_='td3')
    schedule_title = title_element.text.strip() if title_element else "本周课程表"
    
    # 查找课表的主体 table
    table = soup.find('table', class_='table1')
    if not table:
        print("[-] 未能在页面中找到课表对应的表格(class=table1)")
        return None
        
    print("[+] 成功解析出课表框架，正在生成排版...")
    
    # 开始生成 PushPlus 所需的精美 HTML
    html_out = f"""
    <div style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;">
        <h3 style="color: #009689; text-align: center;">{schedule_title}</h3>
        <table border="1" cellpadding="5" cellspacing="0" style="width: 100%; border-collapse: collapse; text-align: center; font-size: 14px;">
            <tr style="background-color: #f2f2f2; color: #333;">
                <th style="width: 16%;">节次</th>
                <th style="width: 16%;">周一</th>
                <th style="width: 16%;">周二</th>
                <th style="width: 16%;">周三</th>
                <th style="width: 16%;">周四</th>
                <th style="width: 16%;">周五</th>
            </tr>
    """
    
    # 遍历1到11节课
    colors = ['#e0f7fa', '#fff9c4', '#f1f8e9', '#ffebee', '#f3e5f5'] # 柔和的卡片背景色循环
    color_idx = 0
    
    for i in range(1, 12):
        row_id = f"tr{i}"
        tr = table.find('tr', id=row_id)
        if not tr:
            continue
            
        tds = tr.find_all('td')
        if len(tds) < 6:
            continue
            
        # 第一列是时间节次
        time_text = tds[0].get_text(separator='<br>', strip=True)
        
        row_html = f"<tr><td>{time_text}</td>"
        
        # 后面5列是周一到周五的课
        for j in range(1, 6):
            cell_text = tds[j].get_text(separator='<br>', strip=True)
            # 如果不是空的(&nbsp; 解析后通常为空或只包含空白)
            if cell_text and cell_text != '' and cell_text != '&nbsp;':
                bg_color = colors[color_idx % len(colors)]
                color_idx += 1
                row_html += f'<td style="background-color: {bg_color}; border-radius: 4px; padding: 4px;">{cell_text}</td>'
            else:
                row_html += "<td></td>"
                
        row_html += "</tr>"
        html_out += row_html
        
    html_out += """
        </table>
        <br>
        <p style="font-size: 12px; color: gray; text-align: right;">-- 来自 Antigravity 自动化推送助手 --</p>
    </div>
    """
    
    print("[+] 课表卡片生成完毕！")
    return html_out

def push_to_wechat(html_content):
    if not html_content:
        return
    if "在此处填写" in PUSHPLUS_TOKEN:
        print("[-] 未配置 PushPlus Token，跳过微信推送。")
        return
        
    print("[*] 正在将课表以卡片形式推送到微信...")
    url = "http://www.pushplus.plus/send"
    data = {
        "token": PUSHPLUS_TOKEN,
        "title": "📚 您的本周课表测试已送达",
        "content": html_content,
        "template": "html" # 启用 HTML 模板渲染表格卡片
    }
    
    res = requests.post(url, json=data)
    if res.status_code == 200 and res.json().get('code') == 200:
        print("[+] 微信推送成功！请在手机微信查收。")
    else:
        print("[-] 微信推送失败:", res.text)

if __name__ == "__main__":
    session = login()
    if session:
        # 获取并解析课表，生成精美HTML
        schedule_html = fetch_and_parse_schedule(session)
        # 通过PushPlus推送到手机微信
        push_to_wechat(schedule_html)
