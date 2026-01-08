# 🖥️ Zerion Task Manager

A retro Windows NT Task Manager-styled dashboard for viewing Zerion API wallet data. Built with Flask, styled like it's 1996.

![Windows NT Style](https://img.shields.io/badge/Style-Windows%20NT-blue)
![Python](https://img.shields.io/badge/Python-3.11-green)
![Flask](https://img.shields.io/badge/Flask-3.0.0-black)

## ⚡ Features

- **Portfolio Tab**: View total wallet value, positions count, active chains, and 24h performance
- **Positions Tab**: Browse all fungible token positions with real-time values
- **Transactions Tab**: Transaction history with type, status, and fees
- **NFTs Tab**: NFT holdings with collection info and floor prices
- **Retro UI**: Authentic Windows NT Task Manager aesthetic

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the Server
```bash
python app.py
```

### 3. Open in Browser
Navigate to: **http://localhost:5000**

## 📖 Usage

1. Enter any Ethereum wallet address (ENS names work too!)
2. Click "Load Wallet Data"
3. Browse through tabs to explore on-chain data

### Example Wallets to Try:
- **vitalik.eth**: `0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045`
- **OpenSea**: `0x5b3256965e7C3cF26E11FCAf296DfC8807C01073`
- **Coinbase**: `0x71660c4005ba85c37ccec55d0c4493e66fe775d3`

## 🎨 Design

Pixel-perfect recreation of Windows NT Task Manager including:
- Classic window chrome with title bar
- Tabbed interface
- Menu bar (non-functional, purely aesthetic)
- Status bar with real-time updates
- Retro green-on-black terminal displays
- Windows 95/NT button styling

## 🔧 Tech Stack

- **Backend**: Flask (Python)
- **Frontend**: Vanilla JavaScript
- **API**: Zerion API v1
- **Styling**: Pure CSS (no frameworks)

## 📡 API Endpoints

The Flask server proxies these Zerion API endpoints:
- `/api/portfolio/<address>` - Portfolio overview
- `/api/positions/<address>` - Fungible positions
- `/api/transactions/<address>` - Transaction history
- `/api/nfts/<address>` - NFT holdings
- `/api/chains` - Supported chains

## 🎯 Viral Potential

Perfect for:
- Screenshots on Twitter/Farcaster
- Tech nostalgia memes
- Crypto + retro aesthetic crossover
- Internal team dashboards
- Conference demos

## 📝 Notes

- Uses Zerion dev API key (replace with your own for production)
- Displays first 20 items per tab
- Supports all EVM chains in Zerion
- Real-time data updates on wallet load

## 🤝 Credits

Built with Zerion API: https://developers.zerion.io/

---

**Made with ❤️ and Windows NT nostalgia**
