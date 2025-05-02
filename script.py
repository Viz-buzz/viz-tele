import requests
from datetime import datetime, timedelta
import pytz

LOG_FILE = "execution.log"
open(LOG_FILE, "a").close()

def log_execution():
    now = datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d %H:%M:%S')
    print(f"📝 Script executed at {now}")
    with open(LOG_FILE, "a") as log_file:
        log_file.write(f"Script executed at {now}\n")

API_URL = "https://cvs-data-public.s3.us-east-1.amazonaws.com/last-availability.json"

HEADERS = {
    'User-Agent': 'Mozilla/5.0',
    'Referer': 'https://checkvisaslots.com',
    'Accept-Language': 'en-US,en;q=0.9'
}

BOT_TOKEN = '7254731409:AAGeEsyLi9x4EYdiRA3GuBK_G3fSo79L9Do'
CHAT_IDs = ['1624851640', '7632912613', '1764669281']

def send_telegram_message(message):
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
    for chat_id in CHAT_IDs:
        payload = {
            'chat_id': chat_id,
            'text': message
        }
        try:
            response = requests.post(url, data=payload)
            if response.status_code != 200:
                print(f"❌ Failed to send message to chat ID {chat_id}. Status Code: {response.status_code}")
            else:
                print(f"✅ Message sent to chat ID {chat_id}")
        except requests.exceptions.RequestException as e:
            print(f"❌ Error sending message to chat ID {chat_id}: {e}")

def get_relative_time(createdon_str, now_str=None):
    tz = pytz.timezone('Asia/Kolkata')
    created_time = tz.localize(datetime.strptime(createdon_str, "%Y-%m-%d %H:%M:%S"))
    now = tz.localize(datetime.strptime(now_str, "%Y-%m-%d %H:%M:%S")) if now_str else datetime.now(tz)
    delta = now - created_time
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
    delta = now - created_time
    return int(delta.total_seconds() // 60)

def fetch_f1_slots():
    print("📡 Fetching slot data...")
    try:
        response = requests.get(API_URL, headers=HEADERS)
        if response.status_code != 200:
            print(f"❌ Failed to fetch data. Status Code: {response.status_code}")
            return

        data = response.json()
        f1_slots = data.get('result', {}).get('F-1 (Regular)', [])
        print(f"📦 Total F-1 slots fetched: {len(f1_slots)}")

        now = datetime.now(pytz.timezone('Asia/Kolkata'))
        new_slots = []
        chennai_found = False
        recent_locations = set()

        for slot in f1_slots:
            location_raw = slot.get('visa_location', '').strip()
            location = location_raw.upper()
            minutes_diff = get_minutes_difference(slot['createdon'], now)
            print(f"🕒 Slot at {location_raw} was updated {minutes_diff} min ago.")

            if minutes_diff <= 3:
                print(f"✅ Recent slot found at: {location_raw}")
                recent_locations.add(location_raw)
                if "CHENNAI" in location:
                    print("🎯 Chennai match found.")
                    new_slots.append(slot)
                    chennai_found = True

        print(f"🎯 Chennai found: {chennai_found}")
        print(f"📍 Recent locations: {recent_locations}")

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
                print(f"📤 Sending message for slot: {slot['visa_location']}")
                send_telegram_message(message)
        else:
            if recent_locations:
                locations_str = ', '.join(sorted(recent_locations))
                info_message = f"⚠️ No recent CHENNAI slot found.\nOther recent locations: {locations_str}"
                print(info_message)
                send_telegram_message(info_message)
            else:
                print("ℹ️ No recent F-1 (Regular) slots found at all.")

    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching data: {e}")

if __name__ == "__main__":
    log_execution()
    fetch_f1_slots()
    print("✅ Script finished.")
