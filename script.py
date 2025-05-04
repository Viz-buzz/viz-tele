import requests
from datetime import datetime, timedelta
import pytz

def log_execution():
    now = datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d %H:%M:%S')
    print(f"📝 Script executed at {now}")

API_URL = "https://cvs-data-public.s3.us-east-1.amazonaws.com/last-availability.json"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Referer': 'https://checkvisaslots.com',
    'Accept-Language': 'en-US,en;q=0.9'
}

BOT_TOKEN = '7254731409:AAGeEsyLi9x4EYdiRA3GuBK_G3fSo79L9Do'
CHAT_IDs = ['7632912613', '1764669281']

def send_telegram_message(message):
    print(f"📤 Sending message to Telegram: {message}")
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
    for chat_id in CHAT_IDs:
        payload = {
            'chat_id': chat_id,
            'text': message
        }
        try:
            response = requests.post(url, data=payload)
            print(f"📨 Sent to {chat_id}, status code: {response.status_code}")
            if response.status_code != 200:
                print(f"❌ Failed to send message to chat ID {chat_id}. Status Code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"❌ Error sending message to chat ID {chat_id}: {e}")

def get_relative_time(createdon_str, now_str=None):
    tz = pytz.timezone('Asia/Kolkata')
    created_time = tz.localize(datetime.strptime(createdon_str, "%Y-%m-%d %H:%M:%S"))
    adjusted_time = created_time + timedelta(hours=5, minutes=30)
    now = tz.localize(datetime.strptime(now_str, "%Y-%m-%d %H:%M:%S")) if now_str else datetime.now(tz)
    delta = now - adjusted_time
    total_seconds = int(delta.total_seconds())
    minutes = total_seconds // 60
    hours = minutes // 60
    days = delta.days
    if minutes < 1:
        return "just now"
    elif minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif hours < 24:
        rem_minutes = minutes % 60
        return f"{hours} hour{'s' if hours != 1 else ''}" + (f" {rem_minutes} minute{'s' if rem_minutes != 1 else ''} ago" if rem_minutes else " ago")
    else:
        return f"{days} day{'s' if days != 1 else ''} ago"

def get_minutes_difference(createdon_str, now):
    tz = pytz.timezone('Asia/Kolkata')
    created_time = tz.localize(datetime.strptime(createdon_str, "%Y-%m-%d %H:%M:%S"))
    adjusted_time = created_time + timedelta(hours=5, minutes=30)
    delta = now - adjusted_time
    minutes = int(delta.total_seconds() // 60)
    print(f"⏱️ Minutes difference for slot created at {createdon_str}: {minutes} minutes")
    return minutes

def fetch_f1_slots():
    print("📡 Fetching data from API...")
    try:
        response = requests.get(API_URL, headers=HEADERS)
        print(f"🌐 API Response Code: {response.status_code}")
        if response.status_code != 200:
            print(f"❌ Failed to fetch data. Status Code: {response.status_code}")
            return

        data = response.json()
        f1_slots = data.get('result', {}).get('F-1 (Regular)', [])
        print(f"📦 F-1 slots fetched: {len(f1_slots)} entries")
        now = datetime.now(pytz.timezone('Asia/Kolkata'))

        new_slots = []
        chennai_found = False
        recent_locations = set()

        for slot in f1_slots:
            print(f"🔍 Checking slot: {slot}")
            minutes_diff = get_minutes_difference(slot['createdon'], now)
            if minutes_diff > 2:
                print("⏭️ Slot skipped (older than 3 minutes)")
                continue

            print(f"✅ Slot is recent. Location: {slot['visa_location']}")
            if slot['visa_location'] in ("CHENNAI", "CHENNAI VAC"):
                new_slots.append(slot)
                print("📌 CHENNAI slot added.")
                if slot['visa_location'] == "CHENNAI":
                    chennai_found = True
            else:
                recent_locations.add(slot['visa_location'])

        print(f"🎯 Chennai found: {chennai_found}, Total CHENNAI/CHENNAI VAC slots: {len(new_slots)}")

        if chennai_found and new_slots:
            separator = "---------------------\n🎯 New Slot Batch\n---------------------"
            print(separator)
            send_telegram_message(separator)

            for slot in new_slots:
                readable_time = get_relative_time(slot['createdon'], now.strftime("%Y-%m-%d %H:%M:%S"))
                message = (
                    f"🚨 New F-1 (Regular) slot available!\n"
                    f"Location: {slot['visa_location']}\n"
                    f"Earliest Date: {slot['earliest_date']}\n"
                    f"No of Appointments: {slot['no_of_apnts']}\n"
                    f"Created {readable_time}."
                )
                send_telegram_message(message)
        else:
            print("ℹ️ No CHENNAI slots found.")
            if recent_locations:
                locations_str = ', '.join(sorted(recent_locations))
                print(f"🗺️ Recent Locations within 3 minutes: {locations_str}")

    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching data: {e}")

if __name__ == "__main__":
    log_execution()
    fetch_f1_slots()
    print("✅ Script finished.")
