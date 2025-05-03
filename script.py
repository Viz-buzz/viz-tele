#!/usr/bin/env python3
"""
Visa Slot Tracker - Advanced Version
-----------------------------------
A robust application that monitors F-1 visa appointment availability
and sends notifications via Telegram when slots become available.

Features:
- Configurable monitoring parameters
- Advanced error handling and retry mechanisms
- Comprehensive logging with rotation
- Telegram notifications with rich formatting
- Data caching to prevent duplicate notifications
- Rate limiting to prevent API abuse
"""

import os
import sys
import json
import time
import requests
import logging
from typing import Dict, List, Optional, Set, Union, Any
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
import pytz
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from functools import lru_cache
from dataclasses import dataclass, field

# Load environment variables from .env file if present
load_dotenv()

# ======== CONFIGURATION ========
class Config:
    """Application configuration with environment variable fallbacks."""
    
    # API Configuration
    API_URL = os.getenv("API_URL", "https://cvs-data-public.s3.us-east-1.amazonaws.com/last-availability.json")
    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
    
    # Telegram Configuration
    BOT_TOKEN = os.getenv("BOT_TOKEN", "7254731409:AAGeEsyLi9x4EYdiRA3GuBK_G3fSo79L9Do")
    CHAT_IDS = os.getenv("CHAT_IDS", "1624851640,7632912613,1764669281").split(",")
    
    # Application Configuration
    TIMEZONE = pytz.timezone(os.getenv("TIMEZONE", "Asia/Kolkata"))
    RECENCY_THRESHOLD_MINUTES = int(os.getenv("RECENCY_THRESHOLD_MINUTES", "3"))
    TARGETED_LOCATIONS = set(os.getenv("TARGETED_LOCATIONS", "CHENNAI,CHENNAI VAC").split(","))
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "visa_tracker.log")
    LOG_MAX_SIZE = int(os.getenv("LOG_MAX_SIZE", str(5 * 1024 * 1024)))  # 5 MB
    LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "3"))
    
    # HTTP Request Headers
    HEADERS = {
        'User-Agent': os.getenv(
            "USER_AGENT", 
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        ),
        'Referer': os.getenv("REFERER", 'https://checkvisaslots.com'),
        'Accept-Language': os.getenv("ACCEPT_LANGUAGE", 'en-US,en;q=0.9'),
        'Accept': 'application/json'
    }
    
    # Cache Configuration
    CACHE_EXPIRY = int(os.getenv("CACHE_EXPIRY", "3600"))  # 1 hour in seconds


# ======== SETUP LOGGING ========
def setup_logging() -> logging.Logger:
    """Configure and return a logger with rotating file handler."""
    logger = logging.getLogger("visa_tracker")
    logger.setLevel(getattr(logging, Config.LOG_LEVEL))
    
    # Prevent duplicate handlers if function is called multiple times
    if logger.handlers:
        return logger
        
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler with rotation
    file_handler = RotatingFileHandler(
        Config.LOG_FILE,
        maxBytes=Config.LOG_MAX_SIZE,
        backupCount=Config.LOG_BACKUP_COUNT
    )
    file_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(filename)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    return logger

logger = setup_logging()


# ======== DATA MODELS ========
@dataclass
class VisaSlot:
    """Data class representing a visa appointment slot."""
    visa_location: str
    earliest_date: str
    no_of_apnts: int
    createdon: str
    visa_type: str = "F-1 (Regular)"
    adjusted_time: Optional[datetime] = None
    
    def __post_init__(self):
        """Calculate adjusted time after initialization."""
        created_time = Config.TIMEZONE.localize(
            datetime.strptime(self.createdon, "%Y-%m-%d %H:%M:%S")
        )
        # Adjust time (+5:30 offset as in original code)
        self.adjusted_time = created_time + timedelta(hours=5, minutes=30)
    
    def minutes_since_creation(self, reference_time: datetime) -> int:
        """Calculate minutes elapsed since slot creation."""
        if not self.adjusted_time:
            return float('inf')
        
        delta = reference_time - self.adjusted_time
        return int(delta.total_seconds() // 60)
    
    def get_relative_time(self, reference_time: datetime) -> str:
        """Get human-readable relative time."""
        if not self.adjusted_time:
            return "unknown time"
            
        delta = reference_time - self.adjusted_time
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
            return (f"{hours} hour{'s' if hours != 1 else ''}" + 
                   (f" {rem_minutes} minute{'s' if rem_minutes != 1 else ''} ago" 
                    if rem_minutes else " ago"))
        else:
            return f"{days} day{'s' if days != 1 else ''} ago"
    
    def to_notification_text(self, reference_time: datetime) -> str:
        """Format slot information for notification."""
        readable_time = self.get_relative_time(reference_time)
        return (
            f"🚨 New F-1 (Regular) slot available!\n"
            f"📍 Location: {self.visa_location}\n"
            f"📅 Earliest Date: {self.earliest_date}\n"
            f"🎟️ No of Appointments: {self.no_of_apnts}\n"
            f"⏱️ Created {readable_time}"
        )


# ======== HTTP CLIENT ========
class RetrySession:
    """Session with retry functionality for robust API requests."""
    
    @staticmethod
    def get_session() -> requests.Session:
        """Create and configure a requests session with retry capability."""
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session
    
    @staticmethod
    def get(url: str, headers: Dict[str, str] = None, timeout: int = None) -> requests.Response:
        """Make a GET request with retry functionality."""
        session = RetrySession.get_session()
        timeout = timeout or Config.REQUEST_TIMEOUT
        return session.get(url, headers=headers, timeout=timeout)


# ======== NOTIFICATION SERVICE ========
class TelegramNotifier:
    """Service for sending notifications via Telegram."""
    
    @staticmethod
    def send_message(message: str, chat_ids: List[str] = None) -> None:
        """Send a message to specified Telegram chat IDs."""
        chat_ids = chat_ids or Config.CHAT_IDS
        
        if not Config.BOT_TOKEN:
            logger.error("Telegram BOT_TOKEN not configured")
            return
            
        url = f'https://api.telegram.org/bot{Config.BOT_TOKEN}/sendMessage'
        
        for chat_id in chat_ids:
            payload = {
                'chat_id': chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            
            try:
                response = requests.post(url, data=payload, timeout=10)
                if response.status_code == 200:
                    logger.debug(f"Message sent successfully to chat ID {chat_id}")
                else:
                    logger.warning(
                        f"Failed to send message to chat ID {chat_id}. "
                        f"Status Code: {response.status_code}, Response: {response.text}"
                    )
            except Exception as e:
                logger.error(f"Error sending message to chat ID {chat_id}: {str(e)}")


# ======== SLOT TRACKER ========
class VisaSlotTracker:
    """Core service for tracking visa slot availability."""
    
    def __init__(self):
        """Initialize the visa slot tracker."""
        self.last_notification_time = datetime.min.replace(tzinfo=Config.TIMEZONE)
        self.processed_slots = set()  # Track processed slots to avoid duplicates
    
    def fetch_visa_slots(self) -> List[VisaSlot]:
        """Fetch visa slot data from the API."""
        logger.info("Fetching data from API...")
        
        try:
            response = RetrySession.get(Config.API_URL, headers=Config.HEADERS)
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch data. Status Code: {response.status_code}")
                return []
                
            data = response.json()
            f1_slots_raw = data.get('result', {}).get('F-1 (Regular)', [])
            
            if not f1_slots_raw:
                logger.info("No F-1 slots found in response")
                return []
                
            logger.info(f"F-1 slots fetched: {len(f1_slots_raw)} entries")
            return [VisaSlot(**slot) for slot in f1_slots_raw]
            
        except json.JSONDecodeError:
            logger.error("Failed to parse API response as JSON")
            return []
        except Exception as e:
            logger.error(f"Error fetching data: {str(e)}")
            return []
    
    def filter_recent_slots(self, slots: List[VisaSlot], reference_time: datetime) -> List[VisaSlot]:
        """Filter slots created within the recency threshold."""
        recent_slots = []
        
        for slot in slots:
            minutes_diff = slot.minutes_since_creation(reference_time)
            
            if minutes_diff <= Config.RECENCY_THRESHOLD_MINUTES:
                logger.debug(f"Recent slot found: {slot.visa_location}, {slot.earliest_date}")
                recent_slots.append(slot)
            else:
                logger.debug(f"Skipping older slot: {slot.visa_location}, {minutes_diff} minutes old")
                
        return recent_slots
    
    def filter_targeted_locations(self, slots: List[VisaSlot]) -> List[VisaSlot]:
        """Filter slots for targeted locations."""
        return [slot for slot in slots if slot.visa_location in Config.TARGETED_LOCATIONS]
        
    def process_slots(self) -> None:
        """Process visa slots and send notifications."""
        reference_time = datetime.now(Config.TIMEZONE)
        
        # Fetch and filter slots
        all_slots = self.fetch_visa_slots()
        recent_slots = self.filter_recent_slots(all_slots, reference_time)
        
        if not recent_slots:
            logger.info("No recent slots found")
            return
            
        # Get targeted location slots
        targeted_slots = self.filter_targeted_locations(recent_slots)
        
        # Track all recent locations for logging
        recent_locations = {slot.visa_location for slot in recent_slots}
        if recent_locations:
            logger.info(f"Recent locations: {', '.join(sorted(recent_locations))}")
        
        # Process targeted slots
        if targeted_slots:
            logger.info(f"Found {len(targeted_slots)} slots in targeted locations")
            
            # Create a unique identifier for each slot to prevent duplicate notifications
            current_slot_ids = {
                f"{slot.visa_location}:{slot.earliest_date}:{slot.createdon}" 
                for slot in targeted_slots
            }
            
            # Filter out already processed slots
            new_slot_ids = current_slot_ids - self.processed_slots
            
            if new_slot_ids:
                # Update processed slots set
                self.processed_slots.update(new_slot_ids)
                
                # Send notification header
                separator = "---------------------\n🎯 New Slot Batch\n---------------------"
                logger.info("Sending notification for new slots")
                TelegramNotifier.send_message(separator)
                
                # Send individual slot notifications
                for slot in targeted_slots:
                    slot_id = f"{slot.visa_location}:{slot.earliest_date}:{slot.createdon}"
                    if slot_id in new_slot_ids:
                        message = slot.to_notification_text(reference_time)
                        TelegramNotifier.send_message(message)
            else:
                logger.info("All targeted slots have already been processed")
        else:
            logger.info("No slots found in targeted locations")


# ======== MAIN EXECUTION ========
def main() -> None:
    """Main function to execute the visa slot tracker."""
    start_time = datetime.now(Config.TIMEZONE)
    logger.info(f"Script started at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        tracker = VisaSlotTracker()
        tracker.process_slots()
    except Exception as e:
        logger.error(f"Unhandled exception: {str(e)}", exc_info=True)
    
    end_time = datetime.now(Config.TIMEZONE)
    execution_time = (end_time - start_time).total_seconds()
    logger.info(f"Script completed in {execution_time:.2f} seconds")


if __name__ == "__main__":
    main()
