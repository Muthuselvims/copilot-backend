# app/db/sql_connection.py

import pyodbc
import pandas as pd
import os
import re
from dotenv import load_dotenv

load_dotenv()  # Load values from .env file if present

def get_db_connection():
    # Check if all required environment variables are set
    required_vars = ['SERVER', 'DATABASE', 'UID', 'PWD']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    try:
        conn = pyodbc.connect(
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={os.getenv('SERVER')};"
            f"DATABASE={os.getenv('DATABASE')};"
            f"UID={os.getenv('UID')};"
            f"PWD={os.getenv('PWD')};"
            "Encrypt=yes;TrustServerCertificate=yes;"
        )
        return conn
    except pyodbc.OperationalError as e:
        error_msg = f"Database connection failed: {str(e)}"
        print(f"ERROR: {error_msg}")
        print("Please check your database connection settings:")
        print(f"  SERVER: {os.getenv('SERVER', 'NOT SET')}")
        print(f"  DATABASE: {os.getenv('DATABASE', 'NOT SET')}")
        print(f"  UID: {os.getenv('UID', 'NOT SET')}")
        print(f"  PWD: {'SET' if os.getenv('PWD') else 'NOT SET'}")
        raise ConnectionError(error_msg)

def execute_sql_query(query):
    conn = get_db_connection()
    try:
        try:
            df = pd.read_sql(query, conn)
        except Exception as e:
            msg = str(e)
            if re.search(r"Invalid column name", msg, re.IGNORECASE):
                raise ValueError(f"Database error: {msg}")
            raise
        return df
    finally:
        conn.close()
