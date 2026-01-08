let currentWallet = '';

// Tab switching
function switchTab(tabName) {
    // Hide all tab contents
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });

    // Remove active class from all tabs
    document.querySelectorAll('.tab').forEach(tab => {
        tab.classList.remove('active');
    });

    // Show selected tab content
    document.getElementById(tabName).classList.add('active');

    // Add active class to clicked tab
    event.target.classList.add('active');
}

// Load wallet data
async function loadWallet() {
    const address = document.getElementById('walletAddress').value.trim();

    if (!address) {
        alert('Please enter a wallet address');
        return;
    }

    currentWallet = address;

    // Load all data
    await Promise.all([
        loadPortfolio(address),
        loadPositions(address),
        loadTransactions(address),
        loadNFTs(address)
    ]);

    updateStatusBar(address);
}

// Load Portfolio
async function loadPortfolio(address) {
    const container = document.getElementById('portfolioData');
    container.innerHTML = '<div class="loading">Loading portfolio data...</div>';

    try {
        const response = await fetch(`/api/portfolio/${address}`);
        const data = await response.json();

        if (data.error) {
            container.innerHTML = `<div class="error">Error: ${data.error}</div>`;
            return;
        }

        const portfolio = data.data?.attributes || {};

        container.innerHTML = `
            <div class="stats-grid">
                <div class="panel">
                    <div class="panel-title">Total Value</div>
                    <div class="stat-box">
                        <div class="stat-label">USD Value</div>
                        <div class="stat-value">$${formatNumber(portfolio.total?.value || 0)}</div>
                    </div>
                </div>

                <div class="panel">
                    <div class="panel-title">Positions</div>
                    <div class="stat-box">
                        <div class="stat-label">Total Positions</div>
                        <div class="stat-value">${portfolio.positions_count || 0}</div>
                    </div>
                </div>

                <div class="panel">
                    <div class="panel-title">Chain Distribution</div>
                    <div class="stat-box">
                        <div class="stat-label">Active Chains</div>
                        <div class="stat-value">${portfolio.chains?.length || 0}</div>
                    </div>
                </div>

                <div class="panel">
                    <div class="panel-title">Performance</div>
                    <div class="stat-box">
                        <div class="stat-label">24h Change</div>
                        <div class="stat-value">${portfolio.changes?.percent_1d ? (portfolio.changes.percent_1d * 100).toFixed(2) : '0.00'}%</div>
                    </div>
                </div>
            </div>

            <div class="panel" style="margin-top: 16px;">
                <div class="panel-title">Portfolio History</div>
                <div class="graph-container">
                    <div class="graph"></div>
                </div>
            </div>
        `;
    } catch (error) {
        container.innerHTML = `<div class="error">Error: ${error.message}</div>`;
    }
}

// Load Positions
async function loadPositions(address) {
    const container = document.getElementById('positionsData');
    container.innerHTML = '<div class="loading">Loading positions...</div>';

    try {
        const response = await fetch(`/api/positions/${address}`);
        const data = await response.json();

        if (data.error) {
            container.innerHTML = `<div class="error">Error: ${data.error}</div>`;
            return;
        }

        const positions = data.data || [];

        if (positions.length === 0) {
            container.innerHTML = '<div class="loading">No positions found</div>';
            return;
        }

        let tableHTML = `
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Asset</th>
                        <th>Symbol</th>
                        <th>Chain</th>
                        <th>Quantity</th>
                        <th>Value (USD)</th>
                        <th>Type</th>
                    </tr>
                </thead>
                <tbody>
        `;

        positions.slice(0, 20).forEach(position => {
            const attrs = position.attributes || {};
            const fungible = attrs.fungible_info || {};
            const quantity = attrs.quantity?.float || 0;
            const value = attrs.value || 0;

            tableHTML += `
                <tr>
                    <td>${fungible.name || 'Unknown'}</td>
                    <td>${fungible.symbol || 'N/A'}</td>
                    <td>${attrs.chain || 'N/A'}</td>
                    <td>${formatNumber(quantity)}</td>
                    <td>$${formatNumber(value)}</td>
                    <td>${attrs.type || 'N/A'}</td>
                </tr>
            `;
        });

        tableHTML += '</tbody></table>';
        container.innerHTML = tableHTML;

    } catch (error) {
        container.innerHTML = `<div class="error">Error: ${error.message}</div>`;
    }
}

// Load Transactions
async function loadTransactions(address) {
    const container = document.getElementById('transactionsData');
    container.innerHTML = '<div class="loading">Loading transactions...</div>';

    try {
        const response = await fetch(`/api/transactions/${address}`);
        const data = await response.json();

        if (data.error) {
            container.innerHTML = `<div class="error">Error: ${data.error}</div>`;
            return;
        }

        const transactions = data.data || [];

        if (transactions.length === 0) {
            container.innerHTML = '<div class="loading">No transactions found</div>';
            return;
        }

        let tableHTML = `
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Type</th>
                        <th>Hash</th>
                        <th>Chain</th>
                        <th>Status</th>
                        <th>Fee (USD)</th>
                    </tr>
                </thead>
                <tbody>
        `;

        transactions.slice(0, 20).forEach(tx => {
            const attrs = tx.attributes || {};
            const time = new Date(attrs.mined_at).toLocaleString();
            const hash = attrs.hash ? attrs.hash.substring(0, 10) + '...' : 'N/A';
            const fee = attrs.fee?.value || 0;

            tableHTML += `
                <tr>
                    <td>${time}</td>
                    <td>${attrs.operation_type || 'N/A'}</td>
                    <td>${hash}</td>
                    <td>${attrs.chain || 'N/A'}</td>
                    <td>${attrs.status || 'N/A'}</td>
                    <td>$${formatNumber(fee)}</td>
                </tr>
            `;
        });

        tableHTML += '</tbody></table>';
        container.innerHTML = tableHTML;

    } catch (error) {
        container.innerHTML = `<div class="error">Error: ${error.message}</div>`;
    }
}

// Load NFTs
async function loadNFTs(address) {
    const container = document.getElementById('nftsData');
    container.innerHTML = '<div class="loading">Loading NFTs...</div>';

    try {
        const response = await fetch(`/api/nfts/${address}`);
        const data = await response.json();

        if (data.error) {
            container.innerHTML = `<div class="error">Error: ${data.error}</div>`;
            return;
        }

        const nfts = data.data || [];

        if (nfts.length === 0) {
            container.innerHTML = '<div class="loading">No NFTs found</div>';
            return;
        }

        let tableHTML = `
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Collection</th>
                        <th>Token ID</th>
                        <th>Chain</th>
                        <th>Type</th>
                        <th>Floor Price</th>
                    </tr>
                </thead>
                <tbody>
        `;

        nfts.slice(0, 20).forEach(nft => {
            const attrs = nft.attributes || {};
            const nftInfo = attrs.nft_info || {};
            const collection = nftInfo.collection || {};

            tableHTML += `
                <tr>
                    <td>${collection.name || 'Unknown'}</td>
                    <td>${nftInfo.token_id || 'N/A'}</td>
                    <td>${attrs.chain || 'N/A'}</td>
                    <td>${nftInfo.interface || 'N/A'}</td>
                    <td>$${formatNumber(collection.floor_price || 0)}</td>
                </tr>
            `;
        });

        tableHTML += '</tbody></table>';
        container.innerHTML = tableHTML;

    } catch (error) {
        container.innerHTML = `<div class="error">Error: ${error.message}</div>`;
    }
}

// Update status bar
function updateStatusBar(address) {
    document.getElementById('statusWallet').textContent = `Wallet: ${address.substring(0, 10)}...`;
    document.getElementById('statusTime').textContent = `Updated: ${new Date().toLocaleTimeString()}`;
}

// Format number helper
function formatNumber(num) {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(2) + 'M';
    } else if (num >= 1000) {
        return (num / 1000).toFixed(2) + 'K';
    }
    return num.toFixed(2);
}

// Enter key support
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('walletAddress').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            loadWallet();
        }
    });
});
