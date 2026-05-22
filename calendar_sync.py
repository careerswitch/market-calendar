#!/usr/bin/env python

import os
import logging
from datetime import datetime, timedelta

import icalendar
import pytz
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

logging.basicConfig(
    filename='scraper_log.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

EASTERN_TZ = pytz.timezone('US/Eastern')
BUCHAREST_TZ = pytz.timezone('Europe/Bucharest')


def make_request(url, params=None, timeout=10):
    ua = UserAgent()
    headers = {'User-Agent': ua.random}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=timeout)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as error:
        logging.error(f"Request error occurred: {error}")
        raise


def convert_to_bucharest(date_obj, time_obj):
    naive_dt = datetime.combine(date_obj.date(), time_obj.time())
    eastern_dt = EASTERN_TZ.localize(naive_dt)
    return eastern_dt.astimezone(BUCHAREST_TZ)


def _add_event(calendar, event_name, converted_dt, seen_events):
    """Deduplicates and adds a single event to the shared calendar. Returns True if added."""
    event_id = (event_name, converted_dt.strftime("%A %B %d %Y %I:%M %p"))
    if event_id in seen_events:
        return False
    seen_events.add(event_id)
    ical_event = icalendar.Event()
    ical_event.add("summary", event_name)
    ical_event.add("dtstart", converted_dt)
    ical_event.add("dtend", converted_dt + timedelta(hours=1))
    ical_event.add("dtstamp", datetime.now(tz=pytz.utc))
    calendar.add_component(ical_event)
    return True


def scrape_economic_events(calendar, seen_events):
    try:
        url = "https://tradingeconomics.com/calendar"
        params = {'importance': '3', 'c': 'United States', 'range': 'next_month'}
        response = make_request(url, params=params)
        soup = BeautifulSoup(response.content, "html.parser")
        calendar_table = soup.find(id="calendar")
        if calendar_table is None:
            raise ValueError("Calendar table not found on TradingEconomics webpage.")

        rows = calendar_table.find_all("tr")[1:]
        current_date = None  # reason: uninitialized state causes AttributeError on .date() if first row lacks a date header
        count = 0

        for row in rows:
            date_element = row.find("th", style="text-align: left;")
            if date_element:
                current_date = datetime.strptime(date_element.get_text(strip=True), "%A %B %d %Y")
            if current_date is None:
                continue

            # Country filter: data-country is server-rendered on every event <tr>
            if row.get('data-country', '').lower() != 'united states':
                continue

            # Importance filter: calendar-date-3 class encodes 3-star (high) importance;
            # calendar-date-1/2 would match lower-importance events which we skip
            time_element = row.find(class_="calendar-date-3")
            event_element = row.find(class_="calendar-event")
            if not (time_element and event_element):
                continue

            event_name = event_element.get_text(strip=True)
            time_obj = datetime.strptime(time_element.get_text(strip=True), "%I:%M %p")
            converted_dt = convert_to_bucharest(current_date, time_obj)
            if _add_event(calendar, event_name, converted_dt, seen_events):
                count += 1

        logging.info(f"TradingEconomics scraper: {count} unique events added.")
    except Exception as e:
        logging.error(f"TradingEconomics scraper failed: {e}")


def scrape_market_events(calendar, seen_events):
    try:
        url = os.environ.get("EVENT_URL")
        if url is None:
            raise ValueError("Missing required environment variable: EVENT_URL.")
        response = make_request(url)
        soup = BeautifulSoup(response.content, "html.parser")
        calendar_table = soup.find(id="calendar")
        if calendar_table is None:
            raise ValueError("Calendar table not found on market events webpage.")

        rows = calendar_table.find_all("tr")[1:]
        current_date = None  # reason: uninitialized state causes AttributeError on .date() if first row lacks a date header
        count = 0

        for row in rows:
            date_element = row.find("th")
            if date_element:
                current_date = datetime.strptime(date_element.get_text(strip=True), "%A %B %d %Y")
            if current_date is None:
                continue

            # Country filter: data-country is server-rendered on every event <tr>
            if row.get('data-country', '').lower() != 'united states':
                continue

            # Importance filter: calendar-date-3 class encodes 3-star (high) importance;
            # calendar-date-1/2 would match lower-importance events which we skip
            time_element = row.find(class_="calendar-date-3")
            event_element = row.find(class_="calendar-event")
            if not (time_element and event_element):
                continue

            event_name = event_element.get_text(strip=True)
            time_obj = datetime.strptime(time_element.get_text(strip=True), "%I:%M %p")
            converted_dt = convert_to_bucharest(current_date, time_obj)
            if _add_event(calendar, event_name, converted_dt, seen_events):
                count += 1

        logging.info(f"Market events scraper: {count} unique events added.")
    except Exception as e:
        logging.error(f"Market events scraper failed: {e}")


def save_calendar(calendar):
    try:
        filename = "Market.ics"
        with open(filename, 'wb') as f:
            f.write(calendar.to_ical())
        logging.info(f"Calendar saved locally: {os.path.abspath(filename)}")
    except Exception as e:
        logging.error(f"An error occurred while saving the calendar: {e}")


if __name__ == "__main__":
    logging.info("Starting calendar sync")
    cal = icalendar.Calendar()
    seen_events = set()
    scrape_economic_events(cal, seen_events)
    scrape_market_events(cal, seen_events)
    save_calendar(cal)
    logging.info("Calendar sync complete")
