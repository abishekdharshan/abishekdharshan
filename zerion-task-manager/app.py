from flask import Flask, render_template, jsonify, request
import requests
import os

app = Flask(__name__)

ZERION_API_KEY = "zk_dev_c4a3fb29e7fa40568d8c621f4bf4d822"
ZERION_BASE_URL = "https://api.zerion.io/v1"

def get_headers():
    return {
        "Authorization": f"Bearer {ZERION_API_KEY}",
        "accept": "application/json"
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/portfolio/<address>')
def get_portfolio(address):
    try:
        url = f"{ZERION_BASE_URL}/wallets/{address}/portfolio"
        response = requests.get(url, headers=get_headers())
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/positions/<address>')
def get_positions(address):
    try:
        url = f"{ZERION_BASE_URL}/wallets/{address}/positions"
        response = requests.get(url, headers=get_headers())
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/transactions/<address>')
def get_transactions(address):
    try:
        url = f"{ZERION_BASE_URL}/wallets/{address}/transactions"
        response = requests.get(url, headers=get_headers())
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/nfts/<address>')
def get_nfts(address):
    try:
        url = f"{ZERION_BASE_URL}/wallets/{address}/positions/nft"
        response = requests.get(url, headers=get_headers())
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/chains')
def get_chains():
    try:
        url = f"{ZERION_BASE_URL}/chains"
        response = requests.get(url, headers=get_headers())
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=8080)
