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
logging.basicConfig(filename='scraper_log.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# Function to make HTTP request with proper error handling
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


# Function to determine if daylight saving time is in effect for a given date
def is_dst(date):
    timezone = pytz.timezone('US/Eastern')  # Adjust timezone as per your requirement
    return timezone.localize(date, is_dst=None).dst() != timedelta(0)


# Function to scrape events calendar
def scrape_events_calendar():
    try:
        url = os.environ.get("EVENT_URL")
        response = make_request(url)
        soup = BeautifulSoup(response.content, "html.parser")
        calendar_table = soup.find(id="calendar")
        if calendar_table is None:
            raise ValueError("Calendar table not found on the events webpage.")
        rows = calendar_table.find("tbody").find_all("tr") # Added tbody to specifically target the body of the table
        current_date = ""
        events = []
        for row in rows:
            date_element = row.find("th")
            if date_element:
                current_date = date_element.get_text(strip=True)
                # Parsing the date with the day of the week
                current_date = datetime.strptime(current_date, "%A %B %d %Y")
            time_element = row.find(class_="calendar-date-3")
            if time_element:
                event_element = row.find(class_="calendar-event")
                if event_element:
                    event = event_element.get_text(strip=True)
                    time_str = time_element.get_text(strip=True)
                    time = datetime.strptime(time_str, "%I:%M %p")
                    if is_dst(current_date):
                        time += timedelta(hours=3)
                    else:
                        time += timedelta(hours=2)
                    time_str_plus_3 = time.strftime("%I:%M %p")
                    events.append(
                        {"date": current_date.strftime("%A %B %d %Y"), "time": time_str_plus_3, "name": event})
        return events
    except Exception as e:
        logging.error(f"An error occurred while scraping the events website: {str(e)}")
        return None


# Function to save calendar to Google Cloud Storage
def save_calendar_to_gcs(calendar):
    try:
        # Save the calendar file locally
        filename = "Market.ics"
        with open(filename, 'wb') as f:
            f.write(calendar.to_ical())

        # Upload the calendar file to GCS
        client = storage.Client() # Changed to use default credentials, which should be set by github action
        bucket_name = "market-calendar-bucket"
        bucket = client.get_bucket(bucket_name)
        blob = bucket.blob(filename)
        blob.upload_from_filename(filename)

        logging.info(f"Calendar uploaded to Google Cloud Storage: gs://{bucket_name}/{filename}")

        # Optional: Remove the local file after uploading to GCS
        os.remove(filename)

    except Exception as e:
        logging.error(f"An error occurred while saving the calendar to Google Cloud Storage: {str(e)}")


# Function to update the calendar
def update_calendar():
    # Scrape events calendar
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

        # Save and upload the calendar to GCS
        save_calendar_to_gcs(economics_calendar)

    else:
        logging.warning("No events found on the events calendar.")


if __name__ == "__main__":
    logging.info("Starting calendar update process")

    # Add logging to print the log file path
    log_file_path = os.path.abspath('scraper_log.log')
    logging.info(f"Log file path: {log_file_path}")

    update_calendar()

    # Add logging to print the log file path after execution
    log_file_path_after = os.path.abspath('scraper_log.log')
    logging.info(f"Log file path after execution: {log_file_path_after}")
