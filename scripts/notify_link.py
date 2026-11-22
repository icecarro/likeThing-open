# -*- coding: utf-8 -*-
"""开机拿到新链接后：生成二维码 + 把链接发到负责人邮箱。"""
import os
import smtplib
import sys
from email.header import Header
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path

import qrcode

BASE = Path(__file__).resolve().parent.parent
url = sys.argv[1] if len(sys.argv) > 1 else ""
if not url:
    print("no url")
    sys.exit(1)

qr_path = BASE / "问卷" / "二维码_当前.png"
img = qrcode.make(url).resize((720, 720))
img.save(qr_path)

host = os.environ.get("SMTP_HOST", "")
user = os.environ.get("SMTP_USER", "")
pwd = os.environ.get("SMTP_PASS", "")
port = int(os.environ.get("SMTP_PORT", "465"))
sender = os.environ.get("SMTP_FROM", user)
if not (host and user and pwd):
    print("SMTP not configured; link saved only")
    sys.exit(0)

msg = MIMEMultipart()
msg["Subject"] = Header("问卷新链接（开机自动发送）", "utf-8")
msg["From"] = formataddr((str(Header("擅长研究所", "utf-8")), sender))
msg["To"] = user
body = f"""电脑已开机，问卷服务已启动。

新链接：
{url}

二维码见附件（二维码_当前.png），直接转发给朋友即可。
"""
msg.attach(MIMEText(body, "plain", "utf-8"))
part = MIMEApplication(qr_path.read_bytes())
part.add_header("Content-Disposition", "attachment", filename=("utf-8", "", "qr.png"))
msg.attach(part)

try:
    with smtplib.SMTP_SSL(host, port, timeout=30) as s:
        s.login(user, pwd)
        s.sendmail(sender, [user], msg.as_string())
    print("mail sent")
except Exception as e:
    print("mail failed", e)
