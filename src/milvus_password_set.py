from pymilvus import connections, utility
import random
import string

# --- Milvus Connection Configuration ---
# These should match your Milvus server configuration
MILVUS_HOST = "localhost"
MILVUS_PORT = "19530"
MILVUS_ALIAS = "password_setter" # Using a specific alias for this script's connection

# --- Administrative Credentials (Assumed Defaults) ---
# This script assumes it can connect with these credentials to perform admin tasks.
ADMIN_USER_FOR_CONNECTION = "root"
ADMIN_PASSWORD_FOR_CONNECTION = "Milvus" # Default password for 'root' user in Milvus

def generate_secure_password(length=16):
    """Generates a cryptographically secure random password."""
    if length < 12:
        print("Warning: Password length is less than 12 characters, which is not recommended.")
    
    characters = string.ascii_letters + string.digits + string.punctuation
    # Ensure at least one of each category if desired, for simplicity just random selection here
    # For stronger passwords, ensure character diversity.
    # Python 3.6+ `random.choices` is good. For older, `SystemRandom` is better.
    try:
        # Use SystemRandom for cryptographically secure random numbers if available
        secure_random = random.SystemRandom()
        password = ''.join(secure_random.choice(characters) for i in range(length))
    except AttributeError:
        # Fallback for environments where SystemRandom might not be fully available (rare)
        password = ''.join(random.choice(characters) for i in range(length))
    return password

def set_milvus_passwords():
    """
    Connects to Milvus using assumed admin credentials, lists all users,
    and resets their passwords to new, randomly generated ones.
    """
    print(f"Attempting to connect to Milvus at {MILVUS_HOST}:{MILVUS_PORT} as user '{ADMIN_USER_FOR_CONNECTION}'...")
    
    admin_connected = False
    try:
        if connections.has_connection(MILVUS_ALIAS):
            connections.remove_connection(MILVUS_ALIAS)

        connections.connect(
            alias=MILVUS_ALIAS,
            host=MILVUS_HOST,
            port=MILVUS_PORT,
            user=ADMIN_USER_FOR_CONNECTION,
            password=ADMIN_PASSWORD_FOR_CONNECTION
        )
        print(f"Successfully connected as '{ADMIN_USER_FOR_CONNECTION}'.")
        admin_connected = True

        print("\n--- Starting Password Reset Process ---")
        print("WARNING: This script will attempt to reset passwords for ALL users.")
        print("Make sure to save the new passwords displayed below.")

        user_info = utility.list_users(include_role_info=False, using=MILVUS_ALIAS)
        
        if not user_info or not user_info.groups:
            print("No users found to reset.")
            return

        usernames = [user.username for user in user_info.groups]
        print(f"Found users: {', '.join(usernames)}\n")

        for user_item in user_info.groups:
            username = user_item.username
            new_generated_password = generate_secure_password()
            
            # Determine the old password to use
            old_password_to_use = "" # Default: empty string for other users, hoping admin override works
            if username == ADMIN_USER_FOR_CONNECTION:
                old_password_to_use = ADMIN_PASSWORD_FOR_CONNECTION
            
            try:
                print(f"Attempting to reset password for user: '{username}'...")
                # Call with three main arguments: username, old_password_to_use, new_generated_password
                utility.reset_password(username, old_password_to_use, new_generated_password, using=MILVUS_ALIAS)
                print(f"  Successfully reset password for user: '{username}'")
                print(f"  New Password for '{username}': {new_generated_password}")
                if username == ADMIN_USER_FOR_CONNECTION:
                    print(f"  IMPORTANT: The password for the admin user '{ADMIN_USER_FOR_CONNECTION}' itself has been changed to: {new_generated_password}")
                    print(f"  You will need this new password for future admin operations or if you re-run this script.")
            except Exception as e_reset:
                print(f"  Failed to reset password for user '{username}'. Error: {e_reset}")
            print("-" * 20)

    except Exception as e_conn:
        print(f"Error during Milvus operation: {e_conn}")
        print("\n--- Troubleshooting ---")
        print("Please ensure the following:")
        print("1. Milvus server is running and accessible.")
        print("2. Authentication IS ENABLED in your Milvus server configuration (e.g., milvus.yaml).")
        print(f"3. The user '{ADMIN_USER_FOR_CONNECTION}' exists and its current password is '{ADMIN_PASSWORD_FOR_CONNECTION}'.")
        print("   If the admin password is not the default 'Milvus', update ADMIN_PASSWORD_FOR_CONNECTION in this script.")
        print("   This script needs administrative privileges to manage user passwords.")

    finally:
        if connections.has_connection(MILVUS_ALIAS):
            connections.disconnect(MILVUS_ALIAS)
            if admin_connected: # Only print if connection was initially successful
                 print(f"\nDisconnected from Milvus alias '{MILVUS_ALIAS}'.")

if __name__ == "__main__":
    print("Milvus Password Setter Script")
    print("="*30)
    set_milvus_passwords()
    print("="*30)
    print("Script finished.")
