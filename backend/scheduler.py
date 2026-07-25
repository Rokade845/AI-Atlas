import asyncio
import threading
from news_service import refresh_all_news

# Configuration: news refresh interval in seconds (default: 30 minutes for batched runs)
REFRESH_INTERVAL = 30 * 60

async def news_scheduler_loop():
    print("Background news scheduler loop started.")
    print(f"Scheduler will run every {REFRESH_INTERVAL} seconds (sleeping first on startup).")
    while True:
        # Sleep first to avoid consuming API quota immediately on boot
        await asyncio.sleep(REFRESH_INTERVAL)
        try:
            print("Scheduler triggering automated news refresh...")
            # Run the synchronous news fetch in a separate thread so it doesn't block the asyncio event loop
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, refresh_all_news)
            print("Scheduler finished news refresh.")
        except Exception as e:
            print(f"Error in background news refresh: {e}")

async def discovery_scheduler_loop():
    print("Background discovery scheduler loop started.")
    DISCOVERY_INTERVAL = 24 * 60 * 60 # 24 hours
    print(f"Discovery scheduler will run every {DISCOVERY_INTERVAL} seconds (sleeping first on startup).")
    
    # Target sectors to cycle through for auto-discovery
    sectors_to_discover = [
        "Brewery AI", "Dairy Processing AI", "Bakery Automation AI", 
        "Meat Processing Inspection", "Fruit and Vegetable Sorting AI", 
        "Beverage Filling Quality Control", "Food Waste Reduction AI",
        "CIP Process Optimization", "Cold Chain Temperature Monitoring"
    ]
    
    import random
    try:
        from discovery_service import run_auto_discovery
    except ImportError:
        print("discovery_service.run_auto_discovery not implemented yet.")
        return
        
    while True:
        # Sleep first to avoid consuming API quota immediately on boot
        await asyncio.sleep(DISCOVERY_INTERVAL)
        try:
            sector = random.choice(sectors_to_discover)
            print(f"Scheduler triggering automated company discovery for sector: '{sector}'...")
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, run_auto_discovery, sector, "Germany")
            print("Scheduler finished automated company discovery.")
        except Exception as e:
            print(f"Error in background company discovery: {e}")

def start_scheduler(app_lifespan_context=None):
    """Starts the news refresh and discovery loops as background asyncio tasks."""
    loop = asyncio.get_event_loop()
    loop.create_task(news_scheduler_loop())
    loop.create_task(discovery_scheduler_loop())
    print("News and Discovery scheduler tasks added to event loop.")
