import time
import datetime
from solana.rpc.api import Client
from solana.transaction import Transaction
from solana.publickey import PublicKey
from solana.keypair import Keypair
from solana.rpc.types import TxOpts
import base58
import struct
import base64
import sqlite3
import os
import json

# Set up client connection
solana_client = Client("https://api.mainnet-beta.solana.com")

# Configuration
PRIVATE_KEY = "YOUR_PRIVATE_KEY_HERE"  # Replace with your private key
wallet = Keypair.from_secret_key(base58.b58decode(PRIVATE_KEY))

# Set token variables
TOKEN_CONTRACT_ADDRESS = "TokenContractAddressHere"  # Replace with the token's contract address
TOKEN_MINT_ADDRESS = "TokenMintAddressHere"  # Replace with the token's mint address
USDT_MINT_ADDRESS = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"  # USDT on Solana

# Raydium DEX program ID
RAYDIUM_LIQUIDITY_PROGRAM_ID = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
RAYDIUM_AMM_PROGRAM_ID = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"

# Database setup
DB_PATH = "solana_transactions.db"


class TransactionDatabase:
    """Database class to store and retrieve transaction information."""

    def __init__(self, db_path=DB_PATH):
        """Initialize database connection and create tables if they don't exist."""
        self.db_path = db_path
        self.connection = None
        self.create_tables()

    def _connect(self):
        """Establish a connection to the SQLite database."""
        if self.connection is None:
            self.connection = sqlite3.connect(self.db_path)
            # Enable foreign keys
            self.connection.execute("PRAGMA foreign_keys = ON")
            # Return dictionary-like rows
            self.connection.row_factory = sqlite3.Row
        return self.connection

    def create_tables(self):
        """Create necessary database tables if they don't exist."""
        conn = self._connect()
        cursor = conn.cursor()

        # Create exchanges table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS exchanges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exchange_id TEXT UNIQUE,
            token_contract TEXT NOT NULL,
            token_mint TEXT NOT NULL,
            base_token_mint TEXT NOT NULL,
            pool_id TEXT NOT NULL,
            wallet_address TEXT NOT NULL,
            exchange_type TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Create transactions table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exchange_id TEXT NOT NULL,
            transaction_type TEXT NOT NULL,
            transaction_signature TEXT NOT NULL,
            amount REAL NOT NULL,
            token_price REAL,
            usdt_amount REAL,
            fee REAL,
            status TEXT NOT NULL,
            raw_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (exchange_id) REFERENCES exchanges(exchange_id)
        )
        ''')

        # Create token_balances table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS token_balances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exchange_id TEXT NOT NULL,
            token_mint TEXT NOT NULL,
            balance_before REAL NOT NULL,
            balance_after REAL NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (exchange_id) REFERENCES exchanges(exchange_id)
        )
        ''')

        conn.commit()

    def start_exchange(self, token_contract, token_mint, base_token_mint,
                       pool_id, wallet_address):
        """Create a new exchange record and return the exchange_id."""
        conn = self._connect()
        cursor = conn.cursor()

        # Generate a unique exchange ID
        exchange_id = f"EX-{int(time.time())}-{os.urandom(4).hex()}"

        cursor.execute(
            '''
        INSERT INTO exchanges (
            exchange_id, token_contract, token_mint, base_token_mint, 
            pool_id, wallet_address, exchange_type, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''',
            (exchange_id, token_contract, token_mint, base_token_mint, pool_id,
             str(wallet_address), "BUY_SELL", "STARTED"))

        conn.commit()
        return exchange_id

    def update_exchange_status(self, exchange_id, status):
        """Update the status of an exchange."""
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute(
            '''
        UPDATE exchanges
        SET status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE exchange_id = ?
        ''', (status, exchange_id))

        conn.commit()

    def record_transaction(self,
                           exchange_id,
                           transaction_type,
                           signature,
                           amount,
                           token_price=None,
                           usdt_amount=None,
                           fee=None,
                           status="COMPLETED",
                           raw_data=None):
        """Record a transaction in the database."""
        conn = self._connect()
        cursor = conn.cursor()

        # Convert raw_data to JSON string if provided
        if raw_data is not None and not isinstance(raw_data, str):
            raw_data = json.dumps(raw_data)

        cursor.execute(
            '''
        INSERT INTO transactions (
            exchange_id, transaction_type, transaction_signature, amount,
            token_price, usdt_amount, fee, status, raw_data
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (exchange_id, transaction_type, signature, amount, token_price,
              usdt_amount, fee, status, raw_data))

        conn.commit()

    def record_token_balance(self, exchange_id, token_mint, balance_before,
                             balance_after):
        """Record token balance changes for an exchange."""
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute(
            '''
        INSERT INTO token_balances (
            exchange_id, token_mint, balance_before, balance_after
        ) VALUES (?, ?, ?, ?)
        ''', (exchange_id, token_mint, balance_before, balance_after))

        conn.commit()

    def get_exchange_history(self, limit=10):
        """Get a list of recent exchanges."""
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute(
            '''
        SELECT e.*, 
               (SELECT COUNT(*) FROM transactions WHERE exchange_id = e.exchange_id) as transaction_count,
               (SELECT SUM(usdt_amount) FROM transactions WHERE exchange_id = e.exchange_id AND transaction_type = 'SELL') - 
               (SELECT SUM(usdt_amount) FROM transactions WHERE exchange_id = e.exchange_id AND transaction_type = 'BUY') as profit
        FROM exchanges e
        ORDER BY e.created_at DESC
        LIMIT ?
        ''', (limit, ))

        return [dict(row) for row in cursor.fetchall()]

    def get_exchange_details(self, exchange_id):
        """Get detailed information about a specific exchange."""
        conn = self._connect()
        cursor = conn.cursor()

        # Get the exchange details
        cursor.execute(
            '''
        SELECT * FROM exchanges WHERE exchange_id = ?
        ''', (exchange_id, ))
        exchange = cursor.fetchone()

        if not exchange:
            return None

        # Get associated transactions
        cursor.execute(
            '''
        SELECT * FROM transactions WHERE exchange_id = ? ORDER BY created_at
        ''', (exchange_id, ))
        transactions = [dict(row) for row in cursor.fetchall()]

        # Get token balance changes
        cursor.execute(
            '''
        SELECT * FROM token_balances WHERE exchange_id = ? ORDER BY timestamp
        ''', (exchange_id, ))
        balances = [dict(row) for row in cursor.fetchall()]

        # Calculate profit/loss
        cursor.execute(
            '''
        SELECT 
            (SELECT SUM(usdt_amount) FROM transactions 
             WHERE exchange_id = ? AND transaction_type = 'SELL') - 
            (SELECT SUM(usdt_amount) FROM transactions 
             WHERE exchange_id = ? AND transaction_type = 'BUY') as profit
        ''', (exchange_id, exchange_id))
        profit_data = cursor.fetchone()

        return {
            'exchange':
            dict(exchange),
            'transactions':
            transactions,
            'balances':
            balances,
            'profit':
            profit_data['profit']
            if profit_data and profit_data['profit'] is not None else 0
        }

    def close(self):
        """Close the database connection."""
        if self.connection is not None:
            self.connection.close()
            self.connection = None


def find_associated_token_address(wallet_address, token_mint_address):
    """Find the associated token account address for a wallet and token mint"""
    seeds = [
        bytes(PublicKey(wallet_address)),
        bytes(PublicKey("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
              ),  # Token program ID
        bytes(PublicKey(token_mint_address))
    ]

    program_id = PublicKey("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
                           )  # Associated token program ID

    return PublicKey.find_program_address(seeds, program_id)[0]


def find_raydium_liquidity_info(token_mint):
    """Find Raydium liquidity info for token"""
    # This is a simplified function - in a real implementation, you would need to query
    # Raydium's liquidity pools to find the correct pool for your token pair

    # Get all accounts owned by Raydium program
    raydium_accounts = solana_client.get_program_accounts(
        PublicKey(RAYDIUM_LIQUIDITY_PROGRAM_ID), encoding="base64")

    # Find the pool that matches our token pair (TOKEN and USDT)
    for account in raydium_accounts:
        try:
            # Parse account data to check if it's the right pool
            # This is simplified - you'd need proper data structure parsing
            data = base64.b64decode(account.account.data[0])

            # Check if this pool contains our token mint and USDT
            # Real implementation would properly decode the AMM data structure
            if TOKEN_MINT_ADDRESS in data or USDT_MINT_ADDRESS in data:
                return {
                    "pool_id":
                    account.pubkey,
                    "authority":
                    PublicKey.find_program_address(
                        [bytes(PublicKey(account.pubkey))],
                        PublicKey(RAYDIUM_AMM_PROGRAM_ID))[0],
                    # Additional pool info would be extracted from data
                }
        except:
            continue

    raise Exception("Raydium liquidity pool not found for token pair")


def swap_token(is_buy, amount, liquidity_info):
    """Execute a swap transaction on Raydium"""
    # This is a simplified implementation
    # In a real implementation, you would:
    # 1. Create a proper Raydium swap instruction
    # 2. Add the instruction to a transaction
    # 3. Sign and send the transaction

    # Example structure of what the real implementation would look like:
    transaction = Transaction()

    # Construct the swap instruction data based on Raydium's interface
    # The actual data structure would depend on Raydium's swap instruction layout
    instruction_data = struct.pack(
        "<BQ",
        0 if is_buy else 1,  # 0 for buy, 1 for sell
        amount)

    # Add the swap instruction
    # transaction.add(...)  # This would be the actual Raydium swap instruction

    # Sign and send transaction
    transaction_signature = solana_client.send_transaction(
        transaction, [wallet],
        opts=TxOpts(skip_preflight=False, preflight_commitment="confirmed"))

    print(
        f"{'Buy' if is_buy else 'Sell'} transaction sent: {transaction_signature['result']}"
    )
    return transaction_signature['result']


def get_token_price(token_mint, usdt_mint):
    """Get approximate token price in USDT."""
    # This is a simplified implementation
    # In a real implementation, you would query the Raydium pool
    # to get the actual price of the token

    # For demonstration purposes, return a mock price
    return 0.05  # Mock price in USDT


def buy_and_sell_token():
    """Main function to buy token, wait, then sell it"""
    # Initialize database
    db = TransactionDatabase()

    try:
        print(f"Finding Raydium liquidity info for {TOKEN_MINT_ADDRESS}...")
        liquidity_info = find_raydium_liquidity_info(TOKEN_MINT_ADDRESS)
        pool_id = str(liquidity_info["pool_id"])
        print(f"Liquidity pool found: {pool_id}")

        # Find token account address
        token_account = find_associated_token_address(wallet.public_key,
                                                      TOKEN_MINT_ADDRESS)
        usdt_account = find_associated_token_address(wallet.public_key,
                                                     USDT_MINT_ADDRESS)

        print(f"Token account address: {token_account}")
        print(f"USDT account address: {usdt_account}")

        # Create exchange record in database
        exchange_id = db.start_exchange(token_contract=TOKEN_CONTRACT_ADDRESS,
                                        token_mint=TOKEN_MINT_ADDRESS,
                                        base_token_mint=USDT_MINT_ADDRESS,
                                        pool_id=pool_id,
                                        wallet_address=str(wallet.public_key))
        print(f"Created exchange record with ID: {exchange_id}")

        # Check USDT balance before
        usdt_balance_info = solana_client.get_token_account_balance(
            usdt_account)
        usdt_balance_before = int(
            usdt_balance_info['result']['value']['amount'])
        usdt_balance_before_decimal = usdt_balance_before / 10**6  # Convert to USDT units
        print(f"USDT Balance Before: {usdt_balance_before_decimal} USDT")

        # Check token balance before
        try:
            token_balance_info = solana_client.get_token_account_balance(
                token_account)
            token_balance_before = int(
                token_balance_info['result']['value']['amount'])
            token_balance_before_decimal = token_balance_before / 10**9  # Assuming 9 decimals for token
        except:
            # Account might not exist yet
            token_balance_before = 0
            token_balance_before_decimal = 0
        print(f"Token Balance Before: {token_balance_before_decimal}")

        # Record initial token balances
        db.record_token_balance(
            exchange_id=exchange_id,
            token_mint=USDT_MINT_ADDRESS,
            balance_before=usdt_balance_before_decimal,
            balance_after=
            usdt_balance_before_decimal  # Will be updated after transaction
        )

        db.record_token_balance(
            exchange_id=exchange_id,
            token_mint=TOKEN_MINT_ADDRESS,
            balance_before=token_balance_before_decimal,
            balance_after=
            token_balance_before_decimal  # Will be updated after transaction
        )

        # Get estimated token price
        token_price = get_token_price(TOKEN_MINT_ADDRESS, USDT_MINT_ADDRESS)
        print(f"Estimated token price: {token_price} USDT")

        if usdt_balance_before <= 0:
            raise Exception("Insufficient USDT balance")

        # Buy token with USDT
        amount_to_swap = usdt_balance_before  # Use all USDT balance
        print(f"Buying token with {amount_to_swap / 10**6} USDT...")

        # Estimate amount of tokens to receive
        estimated_tokens = (amount_to_swap / 10**6) / token_price
        print(f"Estimated tokens to receive: {estimated_tokens}")

        buy_tx = swap_token(True, amount_to_swap, liquidity_info)

        # Record the buy transaction
        db.record_transaction(
            exchange_id=exchange_id,
            transaction_type="BUY",
            signature=buy_tx,
            amount=estimated_tokens,
            token_price=token_price,
            usdt_amount=amount_to_swap / 10**6,
            fee=0.0025 * (amount_to_swap / 10**6),  # Assume 0.25% fee
            status="COMPLETED",
            raw_data={
                "pool_id": pool_id,
                "token_mint": TOKEN_MINT_ADDRESS,
                "usdt_mint": USDT_MINT_ADDRESS
            })

        # Wait for transaction confirmation (simplified)
        print("Waiting for transaction confirmation...")
        time.sleep(2)  # In reality, you'd wait for confirmation

        # Update USDT balance after buy
        usdt_balance_info = solana_client.get_token_account_balance(
            usdt_account)
        usdt_balance_after_buy = int(
            usdt_balance_info['result']['value']['amount'])
        usdt_balance_after_buy_decimal = usdt_balance_after_buy / 10**6

        # Update token balance after buy
        token_balance_info = solana_client.get_token_account_balance(
            token_account)
        token_balance_after_buy = int(
            token_balance_info['result']['value']['amount'])
        token_balance_after_buy_decimal = token_balance_after_buy / 10**9  # Assuming 9 decimals

        # Record updated token balances after buy
        db.record_token_balance(exchange_id=exchange_id,
                                token_mint=USDT_MINT_ADDRESS,
                                balance_before=usdt_balance_before_decimal,
                                balance_after=usdt_balance_after_buy_decimal)

        db.record_token_balance(exchange_id=exchange_id,
                                token_mint=TOKEN_MINT_ADDRESS,
                                balance_before=token_balance_before_decimal,
                                balance_after=token_balance_after_buy_decimal)

        print(f"USDT Balance After Buy: {usdt_balance_after_buy_decimal} USDT")
        print(f"Token Balance After Buy: {token_balance_after_buy_decimal}")

        # Update exchange status
        db.update_exchange_status(exchange_id, "WAITING_TO_SELL")

        print("Waiting 10 seconds before selling...")
        time.sleep(10)

        # Get updated token price (might have changed)
        token_price_for_sell = get_token_price(TOKEN_MINT_ADDRESS,
                                               USDT_MINT_ADDRESS)
        print(f"Updated token price for sell: {token_price_for_sell} USDT")

        # Sell all tokens
        print(f"Selling {token_balance_after_buy} tokens...")
        sell_tx = swap_token(False, token_balance_after_buy, liquidity_info)

        # Estimate USDT amount to receive from sell
        estimated_usdt_from_sell = token_balance_after_buy_decimal * token_price_for_sell

        # Record the sell transaction
        db.record_transaction(
            exchange_id=exchange_id,
            transaction_type="SELL",
            signature=sell_tx,
            amount=token_balance_after_buy_decimal,
            token_price=token_price_for_sell,
            usdt_amount=estimated_usdt_from_sell,
            fee=0.0025 * estimated_usdt_from_sell,  # Assume 0.25% fee
            status="COMPLETED",
            raw_data={
                "pool_id": pool_id,
                "token_mint": TOKEN_MINT_ADDRESS,
                "usdt_mint": USDT_MINT_ADDRESS
            })

        # Wait for transaction confirmation
        print("Waiting for sell transaction confirmation...")
        time.sleep(2)  # In reality, you'd wait for confirmation

        # Update balances after sell
        usdt_balance_info = solana_client.get_token_account_balance(
            usdt_account)
        usdt_balance_after_sell = int(
            usdt_balance_info['result']['value']['amount'])
        usdt_balance_after_sell_decimal = usdt_balance_after_sell / 10**6

        try:
            token_balance_info = solana_client.get_token_account_balance(
                token_account)
            token_balance_after_sell = int(
                token_balance_info['result']['value']['amount'])
            token_balance_after_sell_decimal = token_balance_after_sell / 10**9
        except:
            token_balance_after_sell = 0
            token_balance_after_sell_decimal = 0

        # Record final token balances
        db.record_token_balance(exchange_id=exchange_id,
                                token_mint=USDT_MINT_ADDRESS,
                                balance_before=usdt_balance_after_buy_decimal,
                                balance_after=usdt_balance_after_sell_decimal)

        db.record_token_balance(exchange_id=exchange_id,
                                token_mint=TOKEN_MINT_ADDRESS,
                                balance_before=token_balance_after_buy_decimal,
                                balance_after=token_balance_after_sell_decimal)

        # Calculate profit/loss
        profit = usdt_balance_after_sell_decimal - usdt_balance_before_decimal
        profit_percentage = (profit / usdt_balance_before_decimal
                             ) * 100 if usdt_balance_before_decimal > 0 else 0

        print(
            f"USDT Balance After Sell: {usdt_balance_after_sell_decimal} USDT")
        print(f"Token Balance After Sell: {token_balance_after_sell_decimal}")
        print(f"Profit/Loss: {profit} USDT ({profit_percentage:.2f}%)")

        # Update exchange status
        db.update_exchange_status(exchange_id, "COMPLETED")

        print("Buy and sell operations completed successfully")
        print(f"Buy transaction: {buy_tx}")
        print(f"Sell transaction: {sell_tx}")
        print(f"Exchange ID: {exchange_id} (saved in database)")

        # Display exchange summary
        exchange_details = db.get_exchange_details(exchange_id)
        if exchange_details:
            print("\n=== Exchange Summary ===")
            print(f"Exchange ID: {exchange_id}")
            print(f"Token: {TOKEN_MINT_ADDRESS}")
            print(f"Status: {exchange_details['exchange']['status']}")
            print(f"Created at: {exchange_details['exchange']['created_at']}")
            print(f"Profit/Loss: {exchange_details['profit']} USDT")
            print("Transactions:")
            for tx in exchange_details['transactions']:
                print(
                    f"  - {tx['transaction_type']}: {tx['amount']} tokens at {tx['token_price']} USDT"
                )

    except Exception as e:
        print(f"Error: {str(e)}")
        # Update exchange status to failed if it was created
        try:
            if 'exchange_id' in locals():
                db.update_exchange_status(exchange_id, "FAILED")
        except:
            pass

    finally:
        # Close database connection
        db.close()


def view_exchange_history():
    """View history of exchanges from the database."""
    db = TransactionDatabase()
    try:
        exchanges = db.get_exchange_history()

        if not exchanges:
            print("No exchange history found.")
            return

        print("\n=== Exchange History ===")
        for ex in exchanges:
            print(f"Exchange ID: {ex['exchange_id']}")
            print(f"Token: {ex['token_mint']}")
            print(f"Status: {ex['status']}")
            print(f"Date: {ex['created_at']}")
            print(f"Transactions: {ex['transaction_count']}")
            if ex['profit'] is not None:
                print(f"Profit/Loss: {ex['profit']} USDT")
            print("-" * 40)

    finally:
        db.close()


def view_exchange_details(exchange_id):
    """View detailed information about a specific exchange."""
    db = TransactionDatabase()
    try:
        details = db.get_exchange_details(exchange_id)

        if not details:
            print(f"Exchange ID {exchange_id} not found.")
            return

        print("\n=== Exchange Details ===")
        print(f"Exchange ID: {exchange_id}")
        print(f"Token Contract: {details['exchange']['token_contract']}")
        print(f"Token Mint: {details['exchange']['token_mint']}")
        print(f"Base Token: {details['exchange']['base_token_mint']}")
        print(f"Pool ID: {details['exchange']['pool_id']}")
        print(f"Wallet: {details['exchange']['wallet_address']}")
        print(f"Status: {details['exchange']['status']}")
        print(f"Created: {details['exchange']['created_at']}")
        print(f"Updated: {details['exchange']['updated_at']}")
        print(f"Profit/Loss: {details['profit']} USDT")

        print("\nTransactions:")
        for tx in details['transactions']:
            print(f"  - {tx['transaction_type']}: {tx['amount']} tokens")
            print(f"    Price: {tx['token_price']} USDT")
            print(f"    USDT Amount: {tx['usdt_amount']} USDT")
            print(f"    Fee: {tx['fee']} USDT")
            print(f"    Signature: {tx['transaction_signature']}")
            print(f"    Time: {tx['created_at']}")
            print(f"    Status: {tx['status']}")
            print("    " + "-" * 30)

        print("\nBalance Changes:")
        for bal in details['balances']:
            print(f"  - Token: {bal['token_mint']}")
            print(f"    Before: {bal['balance_before']}")
            print(f"    After: {bal['balance_after']}")
            print(
                f"    Change: {bal['balance_after'] - bal['balance_before']}")
            print(f"    Time: {bal['timestamp']}")
            print("    " + "-" * 30)

    finally:
        db.close()


def main_menu():
    """Display a menu for user to choose actions."""
    while True:
        print("\n=== Solana Token Swap with Database ===")
        print("1. Execute Buy & Sell")
        print("2. View Exchange History")
        print("3. View Exchange Details")
        print("4. Exit")

        choice = input("Enter your choice (1-4): ")

        if choice == '1':
            buy_and_sell_token()
        elif choice == '2':
            view_exchange_history()
        elif choice == '3':
            exchange_id = input("Enter Exchange ID: ")
            view_exchange_details(exchange_id)
        elif choice == '4':
            print("Exiting program.")
            break
        else:
            print("Invalid choice. Please try again.")


if __name__ == "__main__":
    main_menu()
