import requests
import os

# For TRX balance
def get_tron_balance(address):
    url = f"https://api.trongrid.io/v1/accounts/{address}"
    response = requests.get(url)
    data = response.json()
    
    if 'data' in data and len(data['data']) > 0:
        tron_balance = data['data'][0]['balance'] / 1000000  # Convert to TRX
        return tron_balance
    else:
        return None

# For USDT on Ethereum
def get_ethereum_balance(address):
    etherscan_api_key = "YOUR_ETHERSCAN_API_KEY"
    url = f"https://api.etherscan.io/api?module=account&action=tokenbalance&contractaddress=0xdac17f958d2ee523a2206206994597c13d831ec7&address={address}&tag=latest&apikey={etherscan_api_key}"
    response = requests.get(url)
    data = response.json()
    
    if data['status'] == '1':
        usdt_balance = int(data['result']) / 10**6  # Convert to USDT
        return usdt_balance
    else:
        return None

# Function to detect crypto type based on address format
def detect_crypto(address):
    if address.startswith("1") or address.startswith("3"):
        return "Bitcoin (BTC)"
    elif address.startswith("0x"):
        return "Ethereum (ETH)"
    elif address.startswith("T"):
        return "Tron (TRX)"
    else:
        return "Unknown or unsupported address"

# Your logo
logo = """
███████╗██╗  ██╗███████╗ █████╗ ███╗   ██╗
██╔════╝██║  ██║██╔════╝██╔══██╗████╗  ██║
█████╗  ███████║███████╗███████║██╔██╗ ██║
██╔══╝  ██╔══██║╚════██║██╔══██║██║╚██╗██║
███████╗██║  ██║███████║██║  ██║██║ ╚████║
╚══════╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═══╝
"""

# Display menu
def show_menu():
    os.system('clear')  # Clear the screen in terminal
    print(logo)
    print("\033[1;32;40m===============================")
    print("1. Check TRX Wallet Balance")
    print("2. Check ETH Wallet Balance (USDT)")
    print("3. Detect Crypto Type from Address")
    print("4. Check Balances from a TXT File")
    print("5. Exit")
    print("===============================")

# User choice
def user_choice():
    choice = input("Enter your choice: ")
    return choice

# Check TRX balance
def check_trx_balance():
    tron_address = input("Enter your TRX address: ")
    tron_balance = get_tron_balance(tron_address)
    if tron_balance is not None:
        print(f"\033[1;34;40mYour TRX balance: {tron_balance} TRX")
    else:
        print("\033[1;31;40mError fetching TRX balance.")

# Check ETH balance (USDT)
def check_eth_balance():
    eth_address = input("Enter your ETH address: ")
    eth_balance = get_ethereum_balance(eth_address)
    if eth_balance is not None:
        print(f"\033[1;34;40mYour USDT balance: {eth_balance} USDT")
    else:
        print("\033[1;31;40mError fetching USDT balance.")

# Detect Crypto Type from Address
def detect_address_crypto():
    address = input("Enter the address: ")
    crypto_type = detect_crypto(address)
    print(f"\033[1;34;40mThis address belongs to: {crypto_type}")

# Check balances from a file
def check_balances_from_file():
    file_path = input("Enter the path to the file containing addresses: ")
    
    if not os.path.exists(file_path):
        print("\033[1;31;40mFile not found.")
        return
    
    with open(file_path, 'r') as file:
        lines = file.readlines()
        for line in lines:
            address = line.strip()
            crypto_type = detect_crypto(address)
            print(f"\033[1;32;40mAddress: {address} - {crypto_type}")
            
            if crypto_type == "Tron (TRX)":
                tron_balance = get_tron_balance(address)
                print(f"\033[1;34;40mTRX balance: {tron_balance} TRX" if tron_balance else "\033[1;31;40mError fetching TRX balance.")
            elif crypto_type == "Ethereum (ETH)":
                eth_balance = get_ethereum_balance(address)
                print(f"\033[1;34;40mUSDT balance: {eth_balance} USDT" if eth_balance else "\033[1;31;40mError fetching USDT balance.")
            else:
                print("\033[1;31;40mUnsupported address or error fetching balance.")

# Main menu and execution
def main():
    while True:
        show_menu()
        choice = user_choice()
        
        if choice == '1':
            check_trx_balance()
        elif choice == '2':
            check_eth_balance()
        elif choice == '3':
            detect_address_crypto()
        elif choice == '4':
            check_balances_from_file()
        elif choice == '5':
            print("\033[1;32;40mExiting program...")
            break
        else:
            print("\033[1;31;40mInvalid choice. Please try again.")

        input("\033[1;33;40mPress ENTER to continue...")

# Run the program
if __name__ == "__main__":
    main()
