#!/usr/bin/env python3
"""
Database Connection Checker
This script helps diagnose database connection issues
"""

import os
import sys
from dotenv import load_dotenv

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

def check_environment_variables():
    """Check if all required environment variables are set"""
    print("=== Environment Variables Check ===")
    
    load_dotenv()  # Load .env file if present
    
    required_vars = {
        'SERVER': 'Database server address',
        'DATABASE': 'Database name',
        'UID': 'Username',
        'PWD': 'Password'
    }
    
    all_set = True
    for var, description in required_vars.items():
        value = os.getenv(var)
        if value:
            # Don't print the actual password for security
            display_value = "***SET***" if var == 'PWD' else value
            print(f"✅ {var}: {display_value} ({description})")
        else:
            print(f"❌ {var}: NOT SET ({description})")
            all_set = False
    
    return all_set

def test_database_connection():
    """Test the actual database connection"""
    print("\n=== Database Connection Test ===")
    
    try:
        from app.db.sql_connection import get_db_connection
        
        print("Attempting to connect to database...")
        conn = get_db_connection()
        print("✅ Database connection successful!")
        
        # Test a simple query
        cursor = conn.cursor()
        cursor.execute("SELECT 1 as test")
        result = cursor.fetchone()
        print(f"✅ Test query successful: {result}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Database connection failed: {str(e)}")
        return False

def create_env_template():
    """Create a template .env file"""
    env_template = """# Database Connection Settings
# Replace these values with your actual database configuration

SERVER=your_server_address
DATABASE=your_database_name
UID=your_username
PWD=your_password

# Example for local SQL Server:
# SERVER=localhost
# DATABASE=InventoryDB
# UID=sa
# PWD=your_password

# Example for Azure SQL:
# SERVER=your-server.database.windows.net
# DATABASE=your-database
# UID=your-username@your-server
# PWD=your-password
"""
    
    env_file = '.env'
    if not os.path.exists(env_file):
        with open(env_file, 'w') as f:
            f.write(env_template)
        print(f"\n📝 Created template .env file: {env_file}")
        print("Please edit this file with your actual database connection details.")
    else:
        print(f"\n📝 .env file already exists: {env_file}")

def main():
    print("Database Connection Diagnostic Tool")
    print("=" * 40)
    
    # Check environment variables
    env_ok = check_environment_variables()
    
    if not env_ok:
        print("\n❌ Some environment variables are missing.")
        create_env_template()
        print("\nPlease set the required environment variables and try again.")
        return
    
    # Test database connection
    conn_ok = test_database_connection()
    
    if conn_ok:
        print("\n🎉 All checks passed! Database connection is working.")
    else:
        print("\n❌ Database connection failed.")
        print("\nTroubleshooting tips:")
        print("1. Check if the database server is running")
        print("2. Verify the server address and port")
        print("3. Ensure the database name is correct")
        print("4. Check username and password")
        print("5. Verify firewall settings allow connections")
        print("6. For Azure SQL, check if your IP is whitelisted")

if __name__ == "__main__":
    main()
