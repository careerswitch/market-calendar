import os
from datetime import datetime, timedelta
import icalendar
import logging
from fake_useragent import UserAgent
import pandas as pd
from google.cloud import storage
import requests
from bs4 import BeautifulSoup
import pytz

# Configure logging
logging.basicConfig(filename='scraper_log.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


def make_request(url, timeout=10):
    ua = UserAgent()
    headers = {'User-Agent': ua.random}
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as error:
        logging.error(f"Request error occurred: {error}")
        raise


def scrape_events_calendar():
    try:
        url = os.environ.get("EVENT_URL")
        response = make_request(url)
        soup = BeautifulSoup(response.content, "html.parser")
        calendar_table = soup.find(id="calendar")
        if calendar_table is None:
            raise ValueError("Calendar table not found on the events webpage.")
        rows = calendar_table.find_all("tr")[1:]

        # Define time zones
        eastern_tz = pytz.timezone('US/Eastern')
        romania_tz = pytz.timezone('Europe/Bucharest')

        current_date = None
        events = []
        for row in rows:
            date_element = row.find("th")
            if date_element:
                date_text = date_element.get_text(strip=True)
                current_date = datetime.strptime(date_text, "%A %B %d %Y")
            time_element = row.find(class_="calendar-date-3")
            if time_element and current_date:
                event_element = row.find(class_="calendar-event")
                if event_element:
                    event = event_element.get_text(strip=True)
                    time_str = time_element.get_text(strip=True)
                    naive_time = datetime.strptime(time_str, "%I:%M %p")
                    combined = datetime.combine(current_date.date(), naive_time.time())
                    eastern_time = eastern_tz.localize(combined)
                    romania_time = eastern_time.astimezone(romania_tz)
                    romania_time_str = romania_time.strftime("%I:%M %p")
                    events.append({
                        "date": romania_time.strftime("%A %B %d %Y"),
                        "time": romania_time_str,
                        "name": event
                    })
        return events
    except Exception as e:
        logging.error(f"An error occurred while scraping the events website: {str(e)}")
        return None


def save_calendar_to_gcs(calendar):
    try:
        filename = "Market.ics"
        with open(filename, 'wb') as f:
            f.write(calendar.to_ical())
        client = storage.Client.from_service_account_json(os.environ["GOOGLE_APPLICATION_CREDENTIALS"])
        bucket_name = "market-calendar-bucket"
        bucket = client.get_bucket(bucket_name)
        blob = bucket.blob(filename)
        blob.upload_from_filename(filename)
        logging.info(f"Calendar uploaded to Google Cloud Storage: gs://{bucket_name}/{filename}")
        os.remove(filename)
    except Exception as e:
        logging.error(f"An error occurred while saving the calendar to Google Cloud Storage: {str(e)}")


def update_calendar():
    economic_events = scrape_events_calendar()
    if economic_events:
        economics_calendar = icalendar.Calendar()
        for event in economic_events:
            dt = datetime.strptime(event["date"] + " " + event["time"], "%A %B %d %Y %I:%M %p")
            ical_event = icalendar.Event()
            ical_event.add("summary", event["name"])
            ical_event.add("dtstart", dt)
            ical_event.add("dtend", dt + timedelta(hours=1))
            ical_event.add("dtstamp", datetime.now())
            economics_calendar.add_component(ical_event)
        save_calendar_to_gcs(economics_calendar)
    else:
        logging.warning("No events found on the events calendar.")


if __name__ == "__main__":
    logging.info("Starting calendar update process")
    log_file_path = os.path.abspath('scraper_log.log')
    logging.info(f"Log file path: {log_file_path}")
    update_calendar()
    log_file_path_after = os.path.abspath('scraper_log.log')
    logging.info(f"Log file path after execution: {log_file_path_after}")
