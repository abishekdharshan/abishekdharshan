# Ride Price Comparison Bot

A Telegram bot that compares Uber, Lyft, and Curb prices for rides in NYC.

## Quick Start (5 minutes)

### Step 1: Create your Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Choose a name (e.g., "My Ride Compare")
4. Choose a username (e.g., "myride_compare_bot")
5. Copy the API token BotFather gives you

### Step 2: Set up the bot

```bash
cd ride-compare-bot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file with your token
cp .env.example .env
# Edit .env and paste your bot token
```

### Step 3: Run the bot

```bash
python bot.py
```

### Step 4: Use it!

1. Open Telegram and find your bot by its username
2. Send `/start`
3. Send any NYC destination like "JFK Airport" or "343 Gold Street Brooklyn"
4. Get instant price comparison!

## Features

- Compare Uber X, XL, Comfort, Black
- Compare Lyft, Lyft XL
- Compare Curb (Yellow Taxi)
- Deep links to open each app directly
- Set custom pickup location with `/setpickup`
- Share your location as pickup point

## Commands

- `/start` - Welcome message and instructions
- `/setpickup <address>` - Set your pickup location
- `/help` - Get help

## How it works

The bot uses distance-based fare estimation with NYC's typical ride-share pricing. Prices are estimates and may vary based on:
- Surge/Prime Time pricing
- Traffic conditions
- Time of day
- Your account's promotions

**Always check the actual apps for real-time prices before booking!**

## Deploying to the Cloud (Optional)

To keep the bot running 24/7, deploy to a cloud service:

### Railway (Recommended - Free tier)
1. Push code to GitHub
2. Go to [railway.app](https://railway.app)
3. New Project → Deploy from GitHub repo
4. Add environment variable: `TELEGRAM_BOT_TOKEN`

### Render
1. Go to [render.com](https://render.com)
2. New → Background Worker
3. Connect GitHub repo
4. Add environment variable: `TELEGRAM_BOT_TOKEN`
