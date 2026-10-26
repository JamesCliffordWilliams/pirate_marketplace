import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

from config.db import get_connection

def get_connection(connect_timeout=None):  # Updated by James Williams 10/26/26
    """
    Creates and returns a new PostgreSQL connection
    using environment variables.
    Supports AWS RDS SSL configuration if provided.
    connect_timeout: optional seconds to wait (added by James Williams 10/26/26)
    """

    conn_kwargs = {
        "host": os.getenv("DB_HOST"),
        "dbname": os.getenv("DB_NAME"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "port": int(os.getenv("DB_PORT", 5432)),
    }

    sslmode = os.getenv("DB_SSLMODE")
    sslrootcert = os.getenv("DB_SSLROOTCERT")

    if sslmode:
        conn_kwargs["sslmode"] = sslmode

    if sslrootcert:
        conn_kwargs["sslrootcert"] = sslrootcert

    # Added by James Williams 10/26/26
    if connect_timeout:
        conn_kwargs["connect_timeout"] = connect_timeout

    return psycopg2.connect(**conn_kwargs)
