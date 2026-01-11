"""
Ride Price Comparison Telegram Bot
Compare Uber, Lyft, and Curb prices in NYC
"""

import os
import logging
from math import radians, cos, sin, asin, sqrt
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize geocoder
geolocator = Nominatim(user_agent="ride_compare_bot")

# Default pickup location (can be updated by user)
DEFAULT_PICKUP = {
    "name": "Current Location (Manhattan)",
    "lat": 40.7580,  # Times Square as default
    "lon": -73.9855
}

# NYC Ride pricing models (approximate as of 2024)
# These are estimates - actual prices vary by demand, time, etc.
PRICING = {
    "uber_x": {"base": 2.55, "per_mile": 1.75, "per_min": 0.35, "min_fare": 8.00, "booking_fee": 2.75},
    "uber_xl": {"base": 3.85, "per_mile": 2.85, "per_min": 0.50, "min_fare": 10.00, "booking_fee": 2.75},
    "uber_black": {"base": 8.00, "per_mile": 3.75, "per_min": 0.65, "min_fare": 15.00, "booking_fee": 0},
    "uber_comfort": {"base": 3.00, "per_mile": 2.00, "per_min": 0.40, "min_fare": 10.00, "booking_fee": 2.75},
    "lyft_standard": {"base": 2.00, "per_mile": 1.69, "per_min": 0.36, "min_fare": 7.50, "booking_fee": 2.75},
    "lyft_xl": {"base": 3.50, "per_mile": 2.75, "per_min": 0.48, "min_fare": 10.00, "booking_fee": 2.75},
    "lyft_lux": {"base": 5.00, "per_mile": 3.50, "per_min": 0.60, "min_fare": 15.00, "booking_fee": 0},
    "curb_taxi": {"base": 3.00, "per_mile": 2.50, "flag_drop": 3.50, "min_fare": 3.50, "booking_fee": 0},
}

# Surge multiplier simulation (normally 1.0, can go up to 2.5+ during peak)
SURGE_MULTIPLIER = 1.0


def haversine(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Calculate the great circle distance in miles between two points."""
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    miles = 3956 * c  # Earth radius in miles
    return miles


def estimate_duration(miles: float) -> int:
    """Estimate trip duration in minutes based on NYC average speeds."""
    # NYC average speed ~12 mph in Manhattan, ~20 mph in outer boroughs
    avg_speed = 15  # mph
    return max(5, int((miles / avg_speed) * 60))


def calculate_fare(pricing: dict, miles: float, minutes: int, surge: float = 1.0) -> tuple[float, float]:
    """Calculate estimated fare range."""
    if "flag_drop" in pricing:  # Taxi pricing
        base_fare = pricing["flag_drop"] + (miles * pricing["per_mile"])
        # Taxis don't surge the same way, but can have peak surcharges
        low = max(pricing["min_fare"], base_fare * 0.9)
        high = base_fare * 1.2  # Account for traffic, tips suggestion
    else:
        base_fare = (
            pricing["base"] +
            (miles * pricing["per_mile"]) +
            (minutes * pricing["per_min"]) +
            pricing["booking_fee"]
        )
        # Apply surge and create range
        surged_fare = base_fare * surge
        low = max(pricing["min_fare"], surged_fare * 0.85)
        high = surged_fare * 1.25

    return round(low, 2), round(high, 2)


def geocode_address(address: str, bias_nyc: bool = True) -> dict | None:
    """Geocode an address, with NYC bias."""
    try:
        # Add NYC context if not already present
        if bias_nyc and "ny" not in address.lower() and "new york" not in address.lower():
            address = f"{address}, New York, NY"

        location = geolocator.geocode(address, timeout=10)
        if location:
            return {
                "name": location.address,
                "lat": location.latitude,
                "lon": location.longitude
            }
    except GeocoderTimedOut:
        logger.error("Geocoding timed out")
    except Exception as e:
        logger.error(f"Geocoding error: {e}")
    return None


def get_price_comparison(pickup: dict, dropoff: dict) -> str:
    """Generate price comparison for all services."""
    miles = haversine(pickup["lon"], pickup["lat"], dropoff["lon"], dropoff["lat"])
    minutes = estimate_duration(miles)

    # Calculate all fares
    prices = []

    # Uber options
    uber_x = calculate_fare(PRICING["uber_x"], miles, minutes, SURGE_MULTIPLIER)
    uber_xl = calculate_fare(PRICING["uber_xl"], miles, minutes, SURGE_MULTIPLIER)
    uber_comfort = calculate_fare(PRICING["uber_comfort"], miles, minutes, SURGE_MULTIPLIER)
    uber_black = calculate_fare(PRICING["uber_black"], miles, minutes, SURGE_MULTIPLIER)

    # Lyft options
    lyft_std = calculate_fare(PRICING["lyft_standard"], miles, minutes, SURGE_MULTIPLIER)
    lyft_xl = calculate_fare(PRICING["lyft_xl"], miles, minutes, SURGE_MULTIPLIER)

    # Curb/Taxi
    curb = calculate_fare(PRICING["curb_taxi"], miles, minutes)

    # Collect for sorting
    all_rides = [
        ("🚗 Uber X", uber_x, "uber"),
        ("🚙 Uber XL", uber_xl, "uber"),
        ("✨ Uber Comfort", uber_comfort, "uber"),
        ("🖤 Uber Black", uber_black, "uber"),
        ("🩷 Lyft", lyft_std, "lyft"),
        ("🩷 Lyft XL", lyft_xl, "lyft"),
        ("🚕 Curb (Taxi)", curb, "curb"),
    ]

    # Sort by lowest price
    all_rides.sort(key=lambda x: x[1][0])
    best_option = all_rides[0]

    # Build response
    response = f"""
🗺 *RIDE COMPARISON*

📍 *From:* {pickup['name'][:50]}...
📍 *To:* {dropoff['name'][:50]}...

📏 *Distance:* {miles:.1f} miles
⏱ *Est. Time:* {minutes} min

━━━━━━━━━━━━━━━━━━━━

*UBER*
  🚗 UberX: ${uber_x[0]:.0f} - ${uber_x[1]:.0f}
  🚙 UberXL: ${uber_xl[0]:.0f} - ${uber_xl[1]:.0f}
  ✨ Comfort: ${uber_comfort[0]:.0f} - ${uber_comfort[1]:.0f}
  🖤 Black: ${uber_black[0]:.0f} - ${uber_black[1]:.0f}

*LYFT*
  🩷 Lyft: ${lyft_std[0]:.0f} - ${lyft_std[1]:.0f}
  🩷 Lyft XL: ${lyft_xl[0]:.0f} - ${lyft_xl[1]:.0f}

*CURB*
  🚕 Taxi: ${curb[0]:.0f} - ${curb[1]:.0f}

━━━━━━━━━━━━━━━━━━━━

💰 *BEST VALUE:* {best_option[0]}
   ${best_option[1][0]:.0f} - ${best_option[1][1]:.0f}

⚠️ _Estimates only. Check apps for live prices._
"""
    return response


def get_deep_links(address: str) -> InlineKeyboardMarkup:
    """Generate deep links to open each app."""
    encoded = address.replace(" ", "+")

    keyboard = [
        [
            InlineKeyboardButton("Open Uber", url=f"uber://?action=setPickup&dropoff[formatted_address]={encoded}"),
            InlineKeyboardButton("Open Lyft", url=f"lyft://ridetype?id=lyft&destination[address]={encoded}")
        ],
        [
            InlineKeyboardButton("Open Curb", url="curb://")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


# === Bot Handlers ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send welcome message."""
    welcome = """
🚗 *Ride Price Comparison Bot* 🚕

Compare Uber, Lyft & Curb prices instantly!

*How to use:*
1️⃣ Send me a destination address
2️⃣ Get instant price comparison
3️⃣ Tap to open your preferred app

*Commands:*
/start - Show this message
/setpickup <address> - Set your pickup location
/help - Get help

Just send an address to get started!

_Example: "JFK Airport" or "123 Broadway, Manhattan"_
"""
    await update.message.reply_text(welcome, parse_mode='Markdown')


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send help message."""
    help_text = """
*Need help?*

📍 *Set your pickup location:*
/setpickup Times Square, NYC

📍 *Get prices to a destination:*
Just type any address like:
- "JFK Airport"
- "343 Gold Street, Brooklyn"
- "Penn Station"

💡 *Tips:*
- Prices are estimates based on distance
- Check apps for real-time surge pricing
- Tap the buttons to open each app directly
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')


async def set_pickup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set custom pickup location."""
    if not context.args:
        await update.message.reply_text(
            "Please provide an address.\nExample: `/setpickup Times Square, NYC`",
            parse_mode='Markdown'
        )
        return

    address = " ".join(context.args)
    location = geocode_address(address)

    if location:
        context.user_data['pickup'] = location
        await update.message.reply_text(
            f"✅ Pickup location set to:\n📍 {location['name']}",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "❌ Couldn't find that address. Try being more specific.",
            parse_mode='Markdown'
        )


async def handle_destination(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle destination address input."""
    destination_text = update.message.text

    # Show typing indicator
    await update.message.chat.send_action("typing")

    # Geocode destination
    dropoff = geocode_address(destination_text)

    if not dropoff:
        await update.message.reply_text(
            "❌ Couldn't find that address. Try:\n"
            "- Adding 'NYC' or 'Brooklyn' etc.\n"
            "- Using a landmark name\n"
            "- Being more specific",
            parse_mode='Markdown'
        )
        return

    # Get pickup (user's saved or default)
    pickup = context.user_data.get('pickup', DEFAULT_PICKUP)

    # Generate comparison
    comparison = get_price_comparison(pickup, dropoff)
    deep_links = get_deep_links(destination_text)

    await update.message.reply_text(
        comparison,
        parse_mode='Markdown',
        reply_markup=deep_links
    )


async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle shared location as pickup point."""
    location = update.message.location
    context.user_data['pickup'] = {
        "name": "📍 Your shared location",
        "lat": location.latitude,
        "lon": location.longitude
    }
    await update.message.reply_text(
        "✅ Got your location! Now send me a destination address.",
        parse_mode='Markdown'
    )


def main() -> None:
    """Start the bot."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")

    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables!")
        print("\n❌ Error: TELEGRAM_BOT_TOKEN not set!")
        print("1. Create a bot with @BotFather on Telegram")
        print("2. Copy the token")
        print("3. Create a .env file with: TELEGRAM_BOT_TOKEN=your_token_here")
        return

    # Create application
    application = Application.builder().token(token).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("setpickup", set_pickup))
    application.add_handler(MessageHandler(filters.LOCATION, handle_location))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_destination))

    # Start polling
    print("🚗 Ride Compare Bot is running!")
    print("Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
