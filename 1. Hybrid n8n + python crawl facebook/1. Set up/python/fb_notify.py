"""
FB NOTIFY - gửi thông báo tiến độ / lỗi của lượt crawl

Chạy: python fb_notify.py --file noi_dung.txt [--level info|ok|error]
      (run_fb_parallel.ps1 ghi nội dung ra file UTF-8 rồi gọi script này, tránh lỗi mã hóa tiếng Việt khi truyền tham số)

Kênh (bật bằng notify_config.json cạnh file này, kênh nào để trống thì bỏ qua):
  - ghi log      : logs\\notify_log.txt (luôn bật)
  - toast Windows: "toast": true  (thông báo góc màn hình máy chạy tool, máy phải đang đăng nhập)
  - Telegram     : "telegram_bot_token" + "telegram_chat_id"  (tạo bot qua @BotFather, nhắn bot một tin rồi lấy chat_id)
  - Webhook      : "webhook_url"  (Slack / Google Chat / Teams: gửi JSON {"text": "..."})
Mọi lỗi gửi chỉ ghi log, không làm hỏng lượt crawl.
"""

import json
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

WORK_DIR = Path(__file__).parent
CONFIG_FILE = WORK_DIR / "notify_config.json"
LOG_FILE = WORK_DIR / "logs" / "notify_log.txt"
ICON = {"info": "ℹ️", "ok": "✅", "error": "🚨"}


def _config():
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _log(line):
    LOG_FILE.parent.mkdir(exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {line}\n")


def _toast(title, text):
    ps = (
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null;"
        "$x = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent('ToastText02');"
        "$n = $x.GetElementsByTagName('text');"
        "$n.Item(0).AppendChild($x.CreateTextNode($env:FB_T)) | Out-Null;"
        "$n.Item(1).AppendChild($x.CreateTextNode($env:FB_B)) | Out-Null;"
        "$t = [Windows.UI.Notifications.ToastNotification]::new($x);"
        "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("
        "'{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\\WindowsPowerShell\\v1.0\\powershell.exe').Show($t)"
    )
    import os
    env = dict(os.environ, FB_T=title, FB_B=text[:250])
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], env=env, timeout=30, capture_output=True)


def _post(url, data, as_json):
    body = json.dumps(data).encode("utf-8") if as_json else urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json" if as_json else "application/x-www-form-urlencoded"})
    urllib.request.urlopen(req, timeout=20).read()


def notify(text, level="info"):
    cfg = _config()
    full = f"{ICON.get(level, '')} {text}"
    _log(f"[{level}] {text.replace(chr(10), ' | ')}")
    if cfg.get("toast", True):
        try:
            _toast("FB Crawl " + ("LỖI" if level == "error" else "tiến độ"), text.replace("\n", " "))
        except Exception as e:
            _log(f"toast lỗi: {e}")
    if cfg.get("telegram_bot_token") and cfg.get("telegram_chat_id"):
        try:
            _post(f"https://api.telegram.org/bot{cfg['telegram_bot_token']}/sendMessage",
                  {"chat_id": cfg["telegram_chat_id"], "text": full}, as_json=False)
        except Exception as e:
            _log(f"telegram lỗi: {e}")
    if cfg.get("webhook_url"):
        try:
            _post(cfg["webhook_url"], {"text": full}, as_json=True)
        except Exception as e:
            _log(f"webhook lỗi: {e}")


if __name__ == "__main__":
    args = sys.argv[1:]
    level = args[args.index("--level") + 1] if "--level" in args else "info"
    if "--file" in args:
        msg = Path(args[args.index("--file") + 1]).read_text(encoding="utf-8-sig").strip()
    else:
        msg = " ".join(a for i, a in enumerate(args) if not a.startswith("--") and (i == 0 or args[i - 1] != "--level")) or "(trống)"
    notify(msg, level)
