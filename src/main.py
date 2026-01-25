import json
import time
import schedule
import logging
import os
import asyncio
from datetime import datetime
from dateutil import parser
from scraper import EventScraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_config():
    """Loads configuration from config.json."""
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json')
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Config file not found at {config_path}")
        return {"sites": [], "schedule_interval_hours": 24}
    except json.JSONDecodeError:
        logger.error(f"Error decoding config file at {config_path}")
        return {"sites": [], "schedule_interval_hours": 24}

def job_wrapper():
    """Synchronous wrapper for the async job."""
    asyncio.run(job())

async def job():
    """The scraping job to be scheduled (Async)."""
    logger.info("Starting scheduled scraping job...")
    config = load_config()
    sites = config.get("sites", [])
    if not sites:
        logger.warning("No sites configured to scrape.")
        return

    scraper = EventScraper()
    events = await scraper.scrape_sites(sites)
    
    # Filter out events with no name or no start date (empty or whitespace only)
    events = [
        e for e in events 
        if e.get('name') and str(e.get('name')).strip() 
        and e.get('startDate') and str(e.get('startDate')).strip()
    ]
    
    # Filter past events if configured
    if config.get("filter_past_events", False):
        logger.info("Filtering out past events...")
        future_events = []
        now = datetime.now()
        for event in events:
            start_date_raw = event.get('startDate')
            try:
                # Fuzzy parsing to handle various formats
                dt = parser.parse(start_date_raw, fuzzy=True)
                # If valid and in the future (or today)
                if dt.date() >= now.date():
                    future_events.append(event)
                else:
                    logger.debug(f"Dropping past event: {event.get('name')} ({start_date_raw})")
            except Exception as e:
                # If we can't parse the date, we probably shouldn't discard it blindly, 
                # but if the user wants strictly *valid* future events, maybe we keeping it is safer 
                # or dropping it is safer? 
                # Let's keep it but log warning, or drop? User said "only contain events where startDate is today or after".
                # If we can't parse, we don't know. 
                # I will default to KEEPING unparseable dates to avoid data loss on bad formats, 
                # unless strictness is required. But usually safe filtering implies dropping definitely past ones.
                # Actually, let's log and KEEP if uncertain, to be non-destructive.
                logger.warning(f"Could not parse date '{start_date_raw}' for event '{event.get('name')}'. Keeping it. Error: {e}")
                future_events.append(event)
        
        logger.info(f"Filtered {len(events) - len(future_events)} past events. Remaining: {len(future_events)}")
        events = future_events
    
    # Save the events to a JSON file
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
    os.makedirs(data_dir, exist_ok=True)
    
    # 1. Initialize events_total.json if it doesn't exist
    total_events_path = os.path.join(data_dir, 'events_total.json')
    if not os.path.exists(total_events_path):
        try:
            with open(total_events_path, 'w', encoding='utf-8') as f:
                json.dump([], f, indent=2)
            logger.info(f"Initialized empty {total_events_path}")
        except Exception as e:
            logger.error(f"Failed to initialize {total_events_path}: {e}")

    # 2. Save Daily File
    date_str = time.strftime("%Y-%m-%d")
    daily_output_path = os.path.join(data_dir, f'events_{date_str}.json')
    
    try:
        with open(daily_output_path, 'w', encoding='utf-8') as f:
            json.dump(events, f, indent=2, ensure_ascii=False)
        logger.info(f"Successfully saved {len(events)} events to {daily_output_path}")
    except Exception as e:
        logger.error(f"Failed to save events to {daily_output_path}: {e}")

    # 3. Append to events_total.json with Deduplication (Check all fields)
    try:
        if os.path.exists(total_events_path):
            with open(total_events_path, 'r', encoding='utf-8') as f:
                try:
                    total_events = json.load(f)
                except json.JSONDecodeError:
                    total_events = []
        else:
            total_events = []
        
        # Create a set of serialized events for O(1) existence check
        # Sorting keys ensures consistent serialization
        existing_signatures = {json.dumps(e, sort_keys=True) for e in total_events}
        
        new_events_count = 0
        for event in events:
            event_sig = json.dumps(event, sort_keys=True)
            if event_sig not in existing_signatures:
                total_events.append(event)
                existing_signatures.add(event_sig) # Add to set to prevent duplicates within the new batch too if any
                new_events_count += 1
        
        if new_events_count > 0:
            with open(total_events_path, 'w', encoding='utf-8') as f:
                json.dump(total_events, f, indent=2, ensure_ascii=False)
            logger.info(f"Appended {new_events_count} new events to {total_events_path}")
        else:
            logger.info("No new unique events to append to total.")

    except Exception as e:
        logger.error(f"Failed to update {total_events_path}: {e}")

    logger.info("Scraping job finished.")

def main():
    logger.info("Starting Eventizer Application...")
    
    # Run once at startup
    job_wrapper()

    # Schedule subsequent runs
    config = load_config()
    interval = config.get("schedule_interval_hours", 24)
    # schedule library is synchronous. We wrapped the async call.
    schedule.every(interval).hours.do(job_wrapper)
    logger.info(f"Scheduled scraping job every {interval} hours.")

    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()
