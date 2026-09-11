from datetime import datetime, timedelta
import random
import uuid

import pandas as pd
from faker import Faker
from azure.identity import DefaultAzureCredential
from azure.storage.filedatalake import DataLakeServiceClient


STORAGE_ACCOUNT = "stnorthmartdev"
FILE_SYSTEM = "unity"
TARGET_DIR = "source/orders/history"

TOTAL_ROWS = 1_000_000
ROWS_PER_FILE = 100_000

fake = Faker()

credential = DefaultAzureCredential()

service_client = DataLakeServiceClient(
    account_url=f"https://{STORAGE_ACCOUNT}.dfs.core.windows.net",
    credential=credential,
)

file_system_client = service_client.get_file_system_client(FILE_SYSTEM)
directory_client = file_system_client.get_directory_client(TARGET_DIR)


def generate_orders(n: int) -> pd.DataFrame:
    rows = []

    start_date = datetime.now() - timedelta(days=365)

    for _ in range(n):
        quantity = random.randint(1, 8)
        unit_price = round(random.uniform(5, 500), 2)

        rows.append(
            {
                "order_id": str(uuid.uuid4()),
                "customer_id": random.randint(1, 100_000),
                "product_id": random.randint(1, 10_000),
                "store_id": random.randint(1, 250),
                "order_timestamp": start_date
                + timedelta(seconds=random.randint(0, 365 * 24 * 3600)),
                "quantity": quantity,
                "unit_price": unit_price,
                "discount": round(random.choice([0, 0, 0, 0.05, 0.10, 0.20]), 2),
                "payment_method": random.choice(
                    ["card", "paypal", "bank_transfer", "cash"]
                ),
                "country": random.choice(
                    ["BE", "FR", "NL", "DE", "LU"]
                ),
                "status": random.choice(
                    ["completed", "completed", "completed", "cancelled", "returned"]
                ),
            }
        )

    return pd.DataFrame(rows)


for batch_no, start in enumerate(range(0, TOTAL_ROWS, ROWS_PER_FILE), start=1):
    df = generate_orders(ROWS_PER_FILE)

    # Stabiliser les types avant écriture Parquet
    df["customer_id"] = df["customer_id"].astype("Int64")
    df["product_id"] = df["product_id"].astype("Int64")
    df["store_id"] = df["store_id"].astype("Int64")
    df["quantity"] = df["quantity"].astype("Int64")
    local_file = f"/tmp/orders_{batch_no:03d}.parquet"

    df.to_parquet(
        local_file,
        engine="pyarrow",
        index=False,
        coerce_timestamps="us",
        allow_truncated_timestamps=True,
    )

    remote_name = f"orders_{batch_no:03d}.parquet"

    file_client = directory_client.get_file_client(remote_name)

    with open(local_file, "rb") as data:
        file_client.upload_data(data, overwrite=True)

    print(
        f"Uploaded batch {batch_no}: "
        f"{remote_name} ({len(df):,} rows)"
    )