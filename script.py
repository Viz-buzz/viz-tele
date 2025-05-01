import requests
from datetime import datetime, timedelta
import pytz

# API endpoint
API_URL = "https://cvs-data-public.s3.us-east-1.amazonaws.com/last-availability.json"

# Headers to avoid 403 Forbidden error
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Referer': 'https://checkvisaslots.com',
    'Accept-Language': 'en-US,en;q=0.9'
}

BOT_TOKEN = '7254731409:AAGeEsyLi9x4EYdiRA3GuBK_G3fSo79L9Do'
CHAT_IDs = ['1624851640', '7632912613']  # List of chat IDs

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
                print(f"Failed to send message to chat ID {chat_id}. Status Code: {response.status_code}")
            else:
                print(f"Message sent to chat ID {chat_id}")
        except requests.exceptions.RequestException as e:
            print(f"Error sending message to chat ID {chat_id}: {e}")

def get_relative_time(createdon_str, now_str=None):
    tz = pytz.timezone('Asia/Kolkata')
    
    # Parse createdon and localize it to Asia/Kolkata timezone
    created_time = tz.localize(datetime.strptime(createdon_str, "%Y-%m-%d %H:%M:%S"))
    
    # Adjust the time by adding 5 hours and 30 minutes (for IST)
    adjusted_time = created_time + timedelta(hours=5, minutes=30)
    
    # Make the current datetime timezone-aware
    now = tz.localize(datetime.strptime(now_str, "%Y-%m-%d %H:%M:%S")) if now_str else datetime.now(tz)

    # Calculate time difference between the adjusted createdon and the current time
    delta = now - adjusted_time
    total_seconds = int(delta.total_seconds())

    minutes = total_seconds // 60
    hours = minutes // 60
    days = delta.days

    # Return the human-readable time difference
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
    
    # Parse createdon and localize it to Asia/Kolkata timezone
    created_time = tz.localize(datetime.strptime(createdon_str, "%Y-%m-%d %H:%M:%S"))
    
    # Adjust the time by adding 5 hours and 30 minutes (for IST)
    adjusted_time = created_time + timedelta(hours=5, minutes=30)
    
    # Calculate the minutes difference
    delta = now - adjusted_time
    return int(delta.total_seconds() // 60)


# Main logic
def fetch_f1_slots():
    print("Checking for F-1 (Regular) slots...")

    try:
        response = requests.get(API_URL, headers=HEADERS)
        if response.status_code != 200:
            print(f"Failed to fetch data. Status Code: {response.status_code}")
            return

        data = response.json()
        f1_slots = data.get('result', {}).get('F-1 (Regular)', [])
        now = datetime.now(pytz.timezone('Asia/Kolkata'))

        recent_slots = []
        print("\nAll F-1 (Regular) slots with their time differences:\n")

        for slot in f1_slots:
            minutes_diff = get_minutes_difference(slot['createdon'], now)
            readable_time = get_relative_time(slot['createdon'], now.strftime("%Y-%m-%d %H:%M:%S"))
            print(f"{slot['visa_location']} - Created {readable_time}")

            # Print each slot with the formatted details
            print(f'''
                    "visa_location": "{slot['visa_location']}",
                    "visa_type": "{slot['visa_type']}",
                    "createdon": "{slot['createdon']}",
                    "no_of_dates": {slot['no_of_dates']},
                    "no_of_apnts": {slot['no_of_apnts']},
                    "earliest_date": "{slot['earliest_date']}"
                    --> {readable_time}
            ''')

            # Check if the slot was created within 5 minutes
            if minutes_diff <= 5:
                message = f"🚨 New F-1 (Regular) slot available!\nLocation: {slot['visa_location']}\nEarliest Date: {slot['earliest_date']}\nCreated {readable_time} ago."
                send_telegram_message(message)
                
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")


# Run the function to check for F-1 slots
if __name__ == "__main__":
    fetch_f1_slots()
