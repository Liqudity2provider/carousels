import asyncio
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
import uvicorn
from dotenv import load_dotenv

from bot import CarouselBot

# Load environment variables
load_dotenv()

# Create FastAPI app
app = FastAPI(title="Carousel Generator", description="Instagram Carousel Generator Bot")

# Create static directory if it doesn't exist
static_dir = Path("static")
static_dir.mkdir(exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    """Root endpoint with basic info"""
    return {
        "message": "Instagram Carousel Generator Bot",
        "status": "running",
        "endpoints": {
            "static_files": "/static/{filename}",
            "health": "/health"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for Railway"""
    return {"status": "healthy"}

@app.get("/static/{filename}")
async def serve_carousel(filename: str):
    """Serve carousel HTML files"""
    file_path = static_dir / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Carousel not found")
    
    if not filename.endswith('.html'):
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    return FileResponse(
        file_path,
        media_type="text/html",
        headers={"Cache-Control": "public, max-age=3600"}
    )

# Global bot instance
bot_instance = None

async def start_bot():
    """Start the Telegram bot"""
    global bot_instance
    try:
        bot_instance = CarouselBot()
        # Start bot in background
        await bot_instance.app.initialize()
        await bot_instance.app.start()
        await bot_instance.app.updater.start_polling()
        print("✅ Telegram bot started successfully")
    except Exception as e:
        print(f"❌ Error starting bot: {e}")

async def stop_bot():
    """Stop the Telegram bot"""
    global bot_instance
    if bot_instance:
        try:
            await bot_instance.app.updater.stop()
            await bot_instance.app.stop()
            await bot_instance.app.shutdown()
            print("✅ Telegram bot stopped successfully")
        except Exception as e:
            print(f"❌ Error stopping bot: {e}")

@app.on_event("startup")
async def startup_event():
    """Start the bot when the server starts"""
    asyncio.create_task(start_bot())

@app.on_event("shutdown")
async def shutdown_event():
    """Stop the bot when the server shuts down"""
    await stop_bot()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=port,
        reload=False
    )
