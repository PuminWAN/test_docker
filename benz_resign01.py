import imaplib
import email
import json
from bs4 import BeautifulSoup
import requests
import datetime
import pytz
import threading
import time

# IMAP configuration
imap_host = 'incoming.inet.co.th'
imap_user = 'thanaree.th@inet.co.th'
imap_pass = 'KPYSVTAMJAZLIDXP'

# Check if an email date is today
def is_today(email_date):
    thailand_tz = pytz.timezone('Asia/Bangkok')
    current_date = datetime.datetime.now(thailand_tz).date()
    return email_date.astimezone(thailand_tz).date() == current_date

# Extract table data from email body
def extract_table_data(body):
    soup = BeautifulSoup(body, 'lxml')
    table = soup.find('table', style=True)
    if not table:
        return {"<thead>": [], "<tbody>": []}

    headers = []
    rows = []

    # Extract headers from <thead>
    thead = table.find('thead')
    if thead:
        header_row = thead.find('tr')
        if header_row:
            headers = [header.get_text(strip=True) for header in header_row.find_all('th')]

    # Extract rows from <tbody>
    tbody = table.find('tbody')
    if tbody:
        for row in tbody.find_all('tr'):
            cols = row.find_all('td')
            if len(cols) == len(headers):
                row_data = {headers[i]: col.get_text(strip=True) for i, col in enumerate(cols)}
                rows.append(row_data)

    return {
        "<thead>": headers,
        "<tbody>": rows
    }

# Fetch latest email for the current day
def fetch_latest_email():
    emails_data = []
    try:
        with imaplib.IMAP4_SSL(imap_host, 993) as mail:
            mail.login(imap_user, imap_pass)
            print("Login successful!")

            mailbox = "INBOX/HRGA/employee"
            mail.select(mailbox)

            status, data = mail.search(None, '(FROM "no-reply@inet.co.th")')

            if status == "OK" and data[0]:
                mail_ids = data[0].split()

                for mail_id in reversed(mail_ids):
                    # Fetch email content
                    status, data = mail.fetch(mail_id, '(RFC822)')
                    msg = email.message_from_bytes(data[0][1])
                    date_ = msg.get('Date')

                    # Check if email is from today
                    if date_:
                        email_date = email.utils.parsedate_to_datetime(date_)
                        if not is_today(email_date):
                            continue

                    subject = email.header.decode_header(msg['subject'])[0][0]
                    if isinstance(subject, bytes):
                        subject = subject.decode()

                    if "[HR] แจ้งพนักงานลาออก ประจำวันที่" in subject:
                        from_ = msg.get('From')
                        to_ = msg.get('To')
                        cc_ = msg.get('Cc')

                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                content_type = part.get_content_type()
                                content_disposition = str(part.get("Content-Disposition"))

                                if "attachment" not in content_disposition:
                                    payload = part.get_payload(decode=True)
                                    if payload:
                                        body += payload.decode()
                        else:
                            payload = msg.get_payload(decode=True)
                            if payload:
                                body = payload.decode()

                        # Extract table data
                        table_data = extract_table_data(body)
                        if table_data:
                            formatted_date = email_date.astimezone(pytz.timezone('Asia/Bangkok')).strftime('%Y-%m-%d %H:%M:%S')

                            emails_data.append({
                                "Subject": subject,
                                "From": from_,
                                "To": to_,
                                "Cc": cc_,
                                "Date": formatted_date,
                                "TableData": table_data
                            })

            else:
                print(f"No emails found from 'no-reply@inet.co.th' in mailbox '{mailbox}'.")

    except imaplib.IMAP4.error as e:
        print(f"IMAP error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    return emails_data

# Send data to Google Sheets
def send_to_google_sheets(data):
    url = "https://script.google.com/macros/s/AKfycbzDzX5hJMZqWfufn_2aK5SbrX04HEwTDLeLgFsp4U62ZNmRitfjvOeBewW4tl58OWtR9w/exec?action=addUser"
    
    for email_data in data:
        if "TableData" in email_data:
            for row in email_data["TableData"]["<tbody>"]:
                payload = json.dumps({
                    "Date": email_data.get("Date", ""),
                    "ลำดับ": row.get("ลำดับ", ""),
                    "รหัสพนักงาน": row.get("รหัสพนักงาน", ""),
                    "คำนำหน้า": row.get("คำนำหน้า", ""),
                    "ชื่อ": row.get("ชื่อ", ""),
                    "นามสกุล": row.get("นามสกุล", ""),
                    "ตำแหน่ง": row.get("ตำแหน่ง", ""),
                    "ฝ่ายงาน": row.get("ฝ่ายงาน", ""),
                    "บริษัท": row.get("บริษัท", ""),
                    "เริ่มงาน": row.get("เริ่มงาน", ""),
                    "ทำงานวันสุดท้าย": row.get("ทำงานวันสุดท้าย", ""),
                    "วันคืนทรัพย์สิน": row.get("วันคืนทรัพย์สิน", ""),
                    "วันลาออกที่มีผลบังคับใช้": row.get("วันลาออกที่มีผลบังคับใช้", ""),
                    "Forward_mail": row.get("Forward mail", "")                    
                })
                headers = {'Content-Type': 'application/json'}
                try:
                    response = requests.post(url, headers=headers, data=payload)
                    response.raise_for_status()
                    print(f"Response from Google Sheets API: {response.text}")
                except requests.exceptions.RequestException as e:
                    print(f"Error sending data to Google Sheets: {e}")

# Notify LINE
def notify_line(emails_data):
    def send_message_to_line(message):
        line_notify_token = '7IyVzOpm3XyTgly5EHRR8Ll5xDl2FsfXc3xINYTjefX'
        line_notify_url = 'https://notify-api.line.me/api/notify'
        headers = {
            'Authorization': f'Bearer {line_notify_token}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        data = {'message': message}
        try:
            response = requests.post(line_notify_url, headers=headers, data=data)
            response.raise_for_status()
            print(f"Response from LINE Notify: {response.text}")
        except requests.exceptions.RequestException as e:
            print(f"Error sending LINE notification: {e}")

    num_resignations = sum(len(email_data["TableData"]["<tbody>"]) for email_data in emails_data)

    if num_resignations == 0:
        message = "\n[HR] วันนี้ทองฟ้าแจ่มใสไม่มีพนักงานลาออกในวันนี้จร้าา🌼"
        send_message_to_line(message)
        return

    latest_email_date = emails_data[0].get("Date", "Unknown Date")
    message = f"\n[HR] แจ้งพนักงานลาออก\n" \
              f"📅วันที่: {latest_email_date}\n" \
              f"🥺จำนวนพนักงานลาออก: {num_resignations}\n\n"

    # ส่งข้อความหลัก
    send_message_to_line(message)

    # ส่งข้อมูลพนักงานแต่ละคน
    for email_data in emails_data:
        for row in email_data["TableData"]["<tbody>"]:
            emp_message = f"🔹 รหัสพนักงาน: {row.get('รหัสพนักงาน', 'N/A')}\n" \
                          f"   ชื่อ: {row.get('ชื่อ', 'N/A')}\n" \
                          f"   นามสกุล: {row.get('นามสกุล', 'N/A')}\n" \
                          f"   ตำแหน่ง: {row.get('ตำแหน่ง', 'N/A')}\n" \
                          f"   ทำงานวันสุดท้าย: {row.get('ทำงานวันสุดท้าย', 'N/A')}\n" \
                          f"   -------------------------\n"
            send_message_to_line(emp_message)

    closing_message = f"🌸   (｡╯︵╰｡)   🌼"
    send_message_to_line(closing_message)

# Scheduled job
def job():
    print(f"Running job at {datetime.datetime.now(pytz.timezone('Asia/Bangkok'))}")
    emails_data = fetch_latest_email()
    
    if emails_data:
        send_to_google_sheets(emails_data)
        notify_line(emails_data)

# Run daily at a specific time
def run_daily_at(hour, minute):
    tz = pytz.timezone('Asia/Bangkok')
    while True:
        now = datetime.datetime.now(tz)
        target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

        if now > target_time:
            target_time += datetime.timedelta(days=1)

        sleep_time = (target_time - now).total_seconds()
        print(f"Waiting for {sleep_time / 3600:.2f} hours until {target_time.strftime('%Y-%m-%d %H:%M:%S')}")

        while sleep_time > 60:
            time.sleep(60)
            now = datetime.datetime.now(tz)
            sleep_time = (target_time - now).total_seconds()

        time.sleep(sleep_time)
        job()

# Start the thread
thread = threading.Thread(target=run_daily_at, args=(9, 00))
thread.start()
