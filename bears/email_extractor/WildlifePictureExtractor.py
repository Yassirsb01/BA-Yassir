from unittest import result

from DBManager import DBManager
from MicrosoftGraphApi import MicrosoftGraphApi
import pytesseract
from PIL import Image, ImageFilter
import io
import re
import datetime
import dotenv
import requests
import time
import os
import base64
import easyocr
import json  #for the processed_emails.json

dotenv.load_dotenv()

# NEU: Datei für verarbeitete E-Mails
PROCESSED_EMAILS_FILE = "processed_emails.json"

class WildlifePictureExtractor:
    database : DBManager
    graph_api : MicrosoftGraphApi
    access_token : str
    reader : easyocr.Reader
    
    def __init__(self):
        """
        
        Initialize the WildlifePictureExtractor with database and Microsoft Graph API instances.
        :return: None
        :rtype: None
        
        """
        self.database = DBManager(os.getenv("DB_HOST"), os.getenv("DB_USER"), os.getenv("DB_PASSWORD"), os.getenv("DB_NAME"))
        self.database.connect()
        self.graph_api = MicrosoftGraphApi()
        self.access_token = self.graph_api.get_access_token()
        self.reader = easyocr.Reader(['en'], verbose=False)
        # NEU: Verarbeitete emails in ne JSON Datei laden, um endlose schleife zu verhindern.
        self.processed_emails = self._load_processed_emails()
        print(f"📧 System gestartet. Bereits verarbeitete E-Mails: {len(self.processed_emails)}")
        
    def extract_images_information(self, image_bytes):
        """
        Extract animal type and timestamp from wildlife camera image using EasyOCR.
        
        :param image_bytes: The binary content of the image.
        :type image_bytes: bytes
        :return: a dict containing information about the image, including whether a bear is detected and the timestamp
        :rtype: dict
        """
        
        extracted_info = {"has_bear" : False, "timestamp" : None}
        
        image = Image.open(io.BytesIO(image_bytes))
        ocr_results = self.reader.readtext(image, detail=0)
        
        for text in ocr_results:
            if "bear" in text.lower():
                extracted_info["has_bear"] = True
                
            timestamp_match = re.search(r'(\d{4})[/](\d{2})[/](\d{2})\s+(\d{2})[.](\d{2})[.](\d{2})', text)
            timestamp_without_space_match = re.search(r'(\d{4})[/](\d{2})[/](\d{2})(\d{2})[.](\d{2})[.](\d{2})', text)

            if timestamp_match or timestamp_without_space_match:
                if timestamp_match:
                    year, month, day, hour, minute, second = timestamp_match.groups()
                else:
                    year, month, day, hour, minute, second = timestamp_without_space_match.groups()
                    
                extracted_info["timestamp"] = datetime.datetime(
                    int(year), int(month), int(day),
                    int(hour), int(minute), int(second)
                )
    
        return extracted_info
        
    def extract_filename_information(self, filename):
        """
        Extract camera ID and timestamp from filename.
        
        :param filename: The name of the attached image file
        :type filename: str
        :return: a dict containing the camera ID and timestamp
        :rtype: dict
        """
        
        result = {"timestamp": None, "camera_id": None}
            
        # There are only two formats known for the filenames, we use them to extract the camera id.
        # Format 1: 001026_t_250721_IMAG0404.jpg
        filename_camera_id_match1 = re.match(r'^(\d{3})(\d{3})_', filename)
        if filename_camera_id_match1:
            result["camera_id"] = (filename_camera_id_match1.group(0)).replace('_', '')
        
        # Format 2: 001_006_2025.07.21.1930_0.jpeg
        filename_camera_id_match2 = re.match(r'^(\d{3})_(\d{3})_', filename)
        if filename_camera_id_match2:
            result["camera_id"] = (filename_camera_id_match2.group(0)).replace('_', '')
        
        # If timestamp not found in image, try to extract from filename
        if result["timestamp"] is None:
            #Format 1 - Pattern: _t_YYMMDD_
            format1_match = re.search(r'_t_(\d{6})_', filename)
            if format1_match:
                date_str = format1_match.group(1)  # "251116"
                try:
                    year = 2000 + int(date_str[0:2])   # 25 → 2025
                    month = int(date_str[2:4])          # 11
                    day = int(date_str[4:6])            # 16
                    result["timestamp"] = datetime.datetime(year, month, day, 12, 0, 0)
                    print(f"✅ Timestamp aus Format 1 extrahiert: {result['timestamp']}")
                except ValueError as e:
                    print(f"Fehler beim Parsen von Format 1: {e}")
            
            # Format 2 - Pattern: _YYYY.MM.DD.HHMM_
            else:
                filename_timestamp_match = re.search(r'_(\d{4})\.(\d{2})\.(\d{2})\.(\d{4})_', filename)
                if filename_timestamp_match:
                    year, month, day, time_str = filename_timestamp_match.groups()
                    hour = time_str[:2]
                    minute = time_str[2:4]
                    result["timestamp"] = datetime.datetime(
                        int(year), int(month), int(day),
                        int(hour), int(minute), 0
                    )
                    print(f"✅ Timestamp aus Format 2 extrahiert: {result['timestamp']}")
        
        return result
    
    def _load_processed_emails(self):
        """
        Load the set of already processed email IDs from file.
        
        :return: Set of processed email IDs
        :rtype: set
        """
        if os.path.exists(PROCESSED_EMAILS_FILE):
            try:
                with open(PROCESSED_EMAILS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    processed_set = set(data.get("processed_ids", []))
                    print(f"✅ Loaded {len(processed_set)} processed email IDs from {PROCESSED_EMAILS_FILE}")
                    return processed_set
            except Exception as e:
                print(f"⚠️ Error loading processed emails: {e}")
                return set()
        else:
            print(f"ℹ️ No processed emails file found. Creating new tracking.")
            return set()

    def _save_processed_emails(self):
        """
        Save the set of processed email IDs to file.
        
        :return: None
        :rtype: None
        """
        try:
            with open(PROCESSED_EMAILS_FILE, 'w', encoding='utf-8') as f:
                json.dump({
                    "processed_ids": list(self.processed_emails),
                    "last_updated": datetime.datetime.now().isoformat()
                }, f, indent=2)
        except Exception as e:
            print(f"⚠️ Error saving processed emails: {e}")

    def _mark_email_processed(self, email_id):
        """
        Mark an email as processed and save to file.
        
        :param email_id: The email ID to mark as processed
        :type email_id: str
        :return: None
        :rtype: None
        """
        self.processed_emails.add(email_id)
        self._save_processed_emails()
        
    def process_emails(self):
        """
        Process emails to extract wildlife pictures and store them in the database.
        """
        try:
            while True:
                # Token in jeder Iteration erneuern (automatischer Silent Refresh)
                self.access_token = self.graph_api.get_access_token()
                HEADERS = {
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json"
                }

                url = (
                f"https://graph.microsoft.com/v1.0/users/{os.getenv("MAILBOX")}/mailFolders/Inbox/messages"
                "?$filter=isRead eq false"
                "&$top=50"
                )
            
                response = requests.get(url, headers=HEADERS)
                response.raise_for_status()
                
                emails = response.json().get("value", [])
                
                for email in emails:
                    email_id = email["id"]
                    
                    # NEU: Überspringe bereits verarbeitete E-Mails
                    if email_id in self.processed_emails:
                        continue
                    
                    print("Processing email ID:", email_id)

                    # ====== NEU: DEBUG OUTPUT ======
                    sender = email.get("from", {}).get("emailAddress", {}).get("address", "")
                    subject = email.get("subject", "N/A")
                    has_attachments = email.get("hasAttachments", False)

                    print(f"  Von: {sender}")
                    print(f"  Betreff: {subject}")
                    print(f"  Hat Attachments: {has_attachments}")
                    print(f"  Erwarteter Sender: {os.getenv('SENDER_MAILBOX')}")
                    print(f"  Sender-Match: {sender.lower() == os.getenv('SENDER_MAILBOX').lower()}")
                    # ====== ENDE DEBUG ======
                    
                    sender = email.get("from", {}).get("emailAddress", {}).get("address", "")
                    
                    if sender.lower() == os.getenv("SENDER_MAILBOX").lower():
                        
                        attachments_url = f"https://graph.microsoft.com/v1.0/users/{os.getenv("MAILBOX")}/messages/{email_id}/attachments"
                        attachments_response = requests.get(attachments_url, headers=HEADERS)
                        attachments_response.raise_for_status()
                        
                        attachments = attachments_response.json().get("value", [])
                        
                        for attachment in attachments:
                            print("Processing attachment:", attachment["name"])
                            
                            if attachment["@odata.type"] == "#microsoft.graph.fileAttachment" and attachment["name"].lower().endswith(('.jpg', '.jpeg')):
                                content_bytes = base64.b64decode(attachment["contentBytes"])
                                image_extracted_info = self.extract_images_information(content_bytes)
                                
                                if image_extracted_info["has_bear"]:
                                    filename_extracted_info = self.extract_filename_information(attachment["name"])
                                    timestamp_info = image_extracted_info["timestamp"] if image_extracted_info["timestamp"] is not None else filename_extracted_info["timestamp"]
                                    
                                    self.database.insert_picture(
                                        filename=attachment["name"],
                                        timestamp=timestamp_info,
                                        image_metadata=content_bytes,
                                        image_type='trail',
                                        device_id=filename_extracted_info["camera_id"],
                                        parsed_successfully=(timestamp_info is not None and filename_extracted_info["camera_id"] is not None)
                                    )
                                    print(f"✅ Bear detected and saved to database")
                                else:
                                    print("No bear detected in image:", attachment["name"])
                                    
                            print("Finished processing attachment:", attachment["name"])
                        
                        print("Finished processing email ID:", email["id"])
                    
                    # ENTFERNT: Die alten mark_read Zeilen (Zeile 174-179)
                    # NEU: Markiere als lokal verarbeitet
                    self._mark_email_processed(email_id)
                    print(f"📝 Marked email as processed locally")
                
                print("Waiting for 10 seconds before checking for new emails...")
                time.sleep(10)
                
        except KeyboardInterrupt:
            print("\n🛑 Stopping email processor...")
            self.database.disconnect()
            print("✅ Database disconnected. Processed emails saved.")          
    
        
if __name__ == "__main__":
    
    extractor = WildlifePictureExtractor()
    extractor.process_emails()