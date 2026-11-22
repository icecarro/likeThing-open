# -*- coding: utf-8 -*-
"""把报告以邮件发给客户。

用法：python scripts/send_email.py --id 13800138000 --to a@b.com

需要环境变量（QQ 邮箱 / 163 / 企业邮箱都可以）：
  SMTP_HOST  如 smtp.qq.com
  SMTP_PORT  465（SSL）
  SMTP_USER  发件账号
  SMTP_PASS  授权码（不是登录密码）
  SMTP_FROM  发件人显示名，可省略（默认用 SMTP_USER）
"""
import argparse
import os
import smtplib
import sys
from email.header import Header
from email.utils import formataddr
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
CUSTOMERS = BASE / "out" / "customers"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    ap.add_argument("--to", required=True)
    ap.add_argument("--name", default="")
    args = ap.parse_args()

    d = CUSTOMERS / args.id
    pdf = d / "report.pdf"
    jpg = d / "report_mobile.jpg"
    if not pdf.exists():
        print("没有报告文件，跳过：", pdf)
        return 1

    host = os.environ.get("SMTP_HOST", "")
    port = int(os.environ.get("SMTP_PORT", "465"))
    user = os.environ.get("SMTP_USER", "")
    pwd = os.environ.get("SMTP_PASS", "")
    sender = os.environ.get("SMTP_FROM", user)
    if not (host and user and pwd):
        print("未配置 SMTP，报告未发送。配置 SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASS 后再运行。")
        return 2

    msg = MIMEMultipart()
    msg["Subject"] = Header("你的职业方向报告", "utf-8")
    msg["From"] = formataddr((str(Header("擅长研究所", "utf-8")), sender))
    msg["To"] = args.to

    body = f"""你好：

这是你的职业方向报告（编号 {args.id}），附件里有两个文件：
- report.pdf：完整报告，适合存档和打印
- report_mobile.jpg：手机长图，适合直接在微信里看

如果你有空，回一句「哪句最像你、哪句最不像」，我会据此再帮你调一版。

—— 擅长研究所
"""
    msg.attach(MIMEText(body, "plain", "utf-8"))

    for f in (pdf, jpg):
        if f.exists():
            part = MIMEApplication(f.read_bytes())
            part.add_header("Content-Disposition", "attachment",
                            filename=("utf-8", "", f.name))
            msg.attach(part)

    try:
        with smtplib.SMTP_SSL(host, port, timeout=30) as s:
            s.login(user, pwd)
            s.sendmail(sender, [args.to], msg.as_string())
        print("已发送 ->", args.to)
        return 0
    except Exception as e:
        print("发送失败：", e)
        return 3


if __name__ == "__main__":
    sys.exit(main())
