#!/usr/bin/env python

import os
from datetime import datetime, timedelta
import icalendar
import logging
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

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
        logging.exception(f"Request error occurred: {error}")
        raise


# Function to scrape events calendar
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
        for row in rows:
            date_element = row.find("th")
            if date_element:
                current_date = date_element.get_text(strip=True)
            time_element = row.find(class_="calendar-date-3")
            if time_element:
                event_element = row.find(class_="calendar-event")
                if event_element:
                    event = event_element.get_text(strip=True)
                    time_str = time_element.get_text(strip=True)
                    time = datetime.strptime(time_str, "%I:%M %p") + timedelta(hours=3)
                    time_str_plus_3 = time.strftime("%I:%M %p")
                    events.append({"date": current_date, "time": time_str_plus_3, "name": event})
        return events
    except Exception as e:
        logging.exception(f"An error occurred while scraping the events website: {str(e)}")
        raise


def parse_date(date_str):
    try:
        # Try parsing with the specified format
        return datetime.strptime(date_str, '%B %d, %Y')
    except ValueError:
        # If the specified format fails, try a more flexible approach
        return datetime.strptime(date_str, '%B %d').replace(year=datetime.now().year)


def extract_data_from_tr(tr):
    cells = tr.find_all('td')
    event = cells[0].text.strip()
    date = cells[1].text.strip()
    status = cells[2].text.strip()
    return event, date, status


def scrape_schedule_calendar():
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPad; CPU OS 12_2 like Mac OS X) '
                          'AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148'
        }
        schedule_url = os.environ.get("SCHEDULE_URL")
        page = requests.get(schedule_url, headers=headers)
        page.raise_for_status()
        soup = BeautifulSoup(page.content, "html.parser")

        # Selector for the parent <tbody> element containing all <tr> elements
        tbody_selector = "body > div.dialog-off-canvas-main-canvas > div > main > div.page__content > article > div > div:nth-child(3) > div.nsdq-l-layout-container--contained.nsdq-l-layout-container.nsdq-u-padding-top-md.nsdq-u-padding-bottom-md > div > div.nsdq-l-grid__item.layout-right-rail > div:nth-child(2) > div > div > table > tbody"

        # Find the parent <tbody> element
        tbody = soup.select_one(tbody_selector)

        if tbody:
            # Find all <tr> elements under the parent <tbody>
            tr_list = tbody.find_all('tr')

            # Initialize an empty list to store calendar events
            cal_events = []

            for tr in tr_list:
                # Extract data from each <tr> element
                event_name, event_date_str, event_status = extract_data_from_tr(tr)

                # Process event_date_str to get a datetime object
                event_date = parse_date(event_date_str)

                # Example: Add event to the list of calendar events
                cal_events.append({
                    'summary': event_name,
                    'dtstart': event_date,
                    'dtend': event_date,
                })

            # Example: Create an iCalendar with all events
            cal = icalendar.Calendar()
            for event_data in cal_events:
                event = icalendar.Event()
                event.add('summary', event_data['summary'])
                event.add('dtstart', event_data['dtstart'])
                event.add('dtend', event_data['dtend'])
                cal.add_component(event)

            return cal

        else:
            logging.warning("Parent <tbody> not found")

    except Exception as e:
        logging.exception(f"An error occurred: {str(e)}")
        raise


def save_calendar_locally(calendar, filename):
    try:
        # Save the calendar file locally
        with open(filename, 'wb') as f:
            f.write(calendar.to_ical())

        logging.info(f"Calendar saved locally: {filename}")

    except Exception as e:
        logging.exception(f"An error occurred while saving the calendar locally: {str(e)}")
        raise


# Function to merge and update the calendar
def update_calendar():
    try:
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
        else:
            logging.warning("No events found on the events calendar.")

        # Scrape schedule calendar
        schedule_calendar = scrape_schedule_calendar()
        if schedule_calendar:
            # Merge calendars
            merged_calendar = icalendar.Calendar()
            merged_calendar.add('prodid', '-//Market Calendar//')
            merged_calendar.add('version', '2.0')
            if economics_calendar:
                for component in economics_calendar.walk():
                    merged_calendar.add_component(component)
            if schedule_calendar:
                for component in schedule_calendar.walk():
                    merged_calendar.add_component(component)

            filename = "Market.ics"
            save_calendar_locally(merged_calendar, filename)
            logging.info("Calendar merged and saved successfully.")

        else:
            logging.warning("No events found on the schedule calendar.")

    except Exception as e:
        logging.exception(f"An error occurred during calendar update: {str(e)}")
        raise


# Run the scraper and update the calendar immediately
update_calendar()

if __name__ == "__main__":
    logging.info("Starting calendar update process")

    # Add logging to print the log file path
    log_file_path = os.path.abspath('scraper_log.log')
    logging.info(f"Log file path: {log_file_path}")

    update_calendar()
    scrape_schedule_calendar()

    # Add logging to print the log file path after execution
    log_file_path_after = os.path.abspath('scraper_log.log')
    logging.info(f"Log file path after execution: {log_file_path_after}")
