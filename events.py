#!/usr/bin/env python

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import logging
from fake_useragent import UserAgent
import pytz

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


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


# Function to scrape financial data
def scrape_financial_data():
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

        # Print the scraped events to the console
        for event in events:
            print(f"Date: {event['date']}, Time: {event['time']}, Event: {event['name']}")

        return events
    except Exception as e:
        logging.error(f"An error occurred while scraping financial data: {str(e)}")


if __name__ == "__main__":
    logging.info("Starting financial data scraping process")
    scrape_financial_data()
