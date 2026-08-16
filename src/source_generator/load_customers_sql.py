import os
import random
from datetime import datetime, timezone

import pyodbc
from faker import Faker


SERVER = "sql-northmart-dev.database.windows.net"
DATABASE = "sqldb-northmart-dev"

SQL_USER = os.environ["NORTHMART_SQL_USER"]
SQL_PASSWORD = os.environ["NORTHMART_SQL_PASSWORD"]

CUSTOMER_COUNT = 100_000
BATCH_SIZE = 1_000

fake = Faker(["fr_BE", "nl_BE"])

CITIES = [
    ("Brussels", "BE"),
    ("Antwerp", "BE"),
    ("Ghent", "BE"),
    ("Liege", "BE"),
    ("Charleroi", "BE"),
    ("Leuven", "BE"),
    ("Namur", "BE"),
    ("Bruges", "BE"),
]

LOYALTY_LEVELS = ["BRONZE", "SILVER", "GOLD"]


def create_connection():
    connection_string = (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={SERVER};"
        f"DATABASE={DATABASE};"
        f"UID={SQL_USER};"
        f"PWD={SQL_PASSWORD};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=30;"
    )

    return pyodbc.connect(connection_string)


def generate_customer(customer_id):
    first_name = fake.first_name()
    last_name = fake.last_name()

    city, country = random.choice(CITIES)

    email = (
        f"{first_name}.{last_name}.{customer_id}"
        "@northmart.example"
    ).lower().replace(" ", "")

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    loyalty_level = random.choices(
        LOYALTY_LEVELS,
        weights=[60, 30, 10],
        k=1,
    )[0]

    return (
        customer_id,
        first_name,
        last_name,
        email,
        city,
        country,
        loyalty_level,
        now,
        now,
    )


def main():
    print("Connecting to Azure SQL...")

    connection = create_connection()
    cursor = connection.cursor()

    cursor.fast_executemany = True

    sql = """
        INSERT INTO dbo.customers (
            customer_id,
            first_name,
            last_name,
            email,
            city,
            country,
            loyalty_level,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    try:
        for start_id in range(
            1,
            CUSTOMER_COUNT + 1,
            BATCH_SIZE,
        ):
            end_id = min(
                start_id + BATCH_SIZE,
                CUSTOMER_COUNT + 1,
            )

            batch = [
                generate_customer(customer_id)
                for customer_id in range(start_id, end_id)
            ]

            cursor.executemany(sql, batch)
            connection.commit()

            print(
                f"Inserted {end_id - 1:,} / "
                f"{CUSTOMER_COUNT:,} customers"
            )

        print("\nCustomer load complete.")

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()


if __name__ == "__main__":
    main()