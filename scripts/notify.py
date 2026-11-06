#!/usr/bin/env python3
"""Send one plain-text email through Resend (used by workflows when a build fails).

    RESEND_API_KEY=… python3 scripts/notify.py "Subject" "Body text"
"""
import json
import os
import sys
import urllib.request


def main():
    subject, text = sys.argv[1], sys.argv[2]
    body = json.dumps({
        "from": os.environ.get("REPORT_EMAIL_FROM", "fournyl.com Monitoring <fournyl-reports@yoanngrange.com>"),
        "to": [os.environ.get("REPORT_EMAIL_TO", "yoann.grange@gmail.com")],
        "subject": subject,
        "text": text,
    }).encode()
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=body,
        headers={"Authorization": f"Bearer {os.environ['RESEND_API_KEY']}", "Content-Type": "application/json",
                 "User-Agent": "fournyl-notify/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        print(resp.read().decode())


if __name__ == "__main__":
    main()
