import pyodbc
import os
from dotenv import load_dotenv

# Load environment variables from the .env file in the same directory as this script
env_path = os.path.join(os.path.dirname(__file__), 'azuree.env')
load_dotenv(env_path)

# Get connection string from environment variable
conn_str = os.getenv('DATABASE_URL')

print("Connection string from env:", conn_str)  # For debugging

try:
    # Try to connect to the database
    conn = pyodbc.connect(conn_str)
    print("Successfully connected to Azure SQL Database!")
    
    # Create a cursor
    cursor = conn.cursor()
    
    # Test a simple query
    cursor.execute("SELECT @@version")
    row = cursor.fetchone()
    print("Database version:", row[0])
    
    # Close the connection
    conn.close()
    
except Exception as e:
    print("Error connecting to the database:")
    print(str(e)) 