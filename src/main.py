import json
import time
import schedule
import logging
import os
import asyncio
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
    
    # Save the events to a JSON file
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
    os.makedirs(data_dir, exist_ok=True)
    output_path = os.path.join(data_dir, 'events.json')
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(events, f, indent=2, ensure_ascii=False)
        logger.info(f"Successfully saved {len(events)} events to {output_path}")
    except Exception as e:
        logger.error(f"Failed to save events to {output_path}: {e}")

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
