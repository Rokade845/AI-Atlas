import asyncio
import threading
from news_service import refresh_all_news

# Configuration: news refresh interval in seconds (default: 6 hours)
REFRESH_INTERVAL = 6 * 60 * 60

async def news_scheduler_loop():
    print("Background news scheduler loop started.")
    # Add a short delay on server startup to prevent immediate API quota consumption
    print("Scheduler waiting 30 seconds before initial news aggregation run...")
    await asyncio.sleep(30)
    while True:
        try:
            print("Scheduler triggering automated news refresh...")
            # Run the synchronous news fetch in a separate thread so it doesn't block the asyncio event loop
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, refresh_all_news)
            print("Scheduler finished news refresh.")
        except Exception as e:
            print(f"Error in background news refresh: {e}")
            
        print(f"Scheduler sleeping for {REFRESH_INTERVAL} seconds.")
        await asyncio.sleep(REFRESH_INTERVAL)

def start_scheduler(app_lifespan_context=None):
    """Starts the news refresh loop as a background asyncio task."""
    loop = asyncio.get_event_loop()
    loop.create_task(news_scheduler_loop())
    print("News scheduler task added to event loop.")
