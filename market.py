import os
from datetime import datetime, timedelta
import icalendar
import logging
from fake_useragent import UserAgent
from google.cloud import storage
import requests
from bs4 import BeautifulSoup
import pytz

# Configure logging
logging.basicConfig(
    filename='scraper_log.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


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


def convert_time_to_eet(date_obj, time_obj):
    # Debugging timezone issue
    print(f"Original date: {date_obj}, time: {time_obj}")

    # Combine date and time
    naive_dt = datetime.combine(date_obj.date(), time_obj.time())

    # Assume original time is in US/Eastern (Confirm this in your data!)
    eastern_tz = pytz.timezone('US/Eastern')
    bucharest_tz = pytz.timezone('Europe/Bucharest')

    eastern_dt = eastern_tz.localize(naive_dt)
    bucharest_dt = eastern_dt.astimezone(bucharest_tz)

    # Debug converted time
    print(f"Converted datetime: {bucharest_dt}")

    return bucharest_dt


def scrape_events_calendar():
    try:
        url = os.environ.get("EVENT_URL")
        response = make_request(url)
        soup = BeautifulSoup(response.content, "html.parser")
        calendar_table = soup.find(id="calendar")

        if calendar_table is None:
            raise ValueError("Calendar table not found on the events webpage.")

        rows = calendar_table.find_all("tr")[1:]
        current_date = ""
        events = []
        seen_events = set()  # Deduplication at scrape time

        for row in rows:
            date_element = row.find("th")
            if date_element:
                current_date_str = date_element.get_text(strip=True)
                current_date = datetime.strptime(current_date_str, "%A %B %d %Y")

            time_element = row.find(class_="calendar-date-3")
            event_element = row.find(class_="calendar-event")

            if time_element and event_element:
                event = event_element.get_text(strip=True)
                time_str = time_element.get_text(strip=True)
                time = datetime.strptime(time_str, "%I:%M %p")

                # Convert time from US/Eastern to Europe/Bucharest
                converted_dt = convert_time_to_eet(current_date, time)

                converted_date_str = converted_dt.strftime("%A %B %d %Y")
                converted_time_str = converted_dt.strftime("%I:%M %p")

                event_id = (event, converted_date_str, converted_time_str)

                if event_id in seen_events:
                    print(f"Duplicate event skipped: {event_id}")
                    continue

                seen_events.add(event_id)

                events.append({
                    "date": converted_date_str,
                    "time": converted_time_str,
                    "name": event
                })

        print(f"Total unique events scraped: {len(events)}")
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

    if not economic_events:
        logging.warning("No events found on the events calendar.")
        return

    economics_calendar = icalendar.Calendar()

    for event in economic_events:
        dt = datetime.strptime(f'{event["date"]} {event["time"]}', "%A %B %d %Y %I:%M %p")
        ical_event = icalendar.Event()
        ical_event.add("summary", event["name"])
        ical_event.add("dtstart", dt)
        ical_event.add("dtend", dt + timedelta(hours=1))
        ical_event.add("dtstamp", datetime.now())
        economics_calendar.add_component(ical_event)

        print(f"Added event: {event['name']} on {event['date']} at {event['time']}")

    save_calendar_to_gcs(economics_calendar)


# Run the scraper and update the calendar only once
if __name__ == "__main__":
    logging.info("Starting calendar update process")
    update_calendar()