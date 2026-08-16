from datetime import datetime
import io
import random
import time
import uuid

import pandas as pd
from azure.identity import DefaultAzureCredential
from azure.storage.filedatalake import DataLakeServiceClient


STORAGE_ACCOUNT = "stnorthmartdev"
FILE_SYSTEM = "unity"
TARGET_DIR = "source/orders/incoming"

ROWS_PER_BATCH = 500
INTERVAL_SECONDS = 30

credential = DefaultAzureCredential()

service_client = DataLakeServiceClient(
    account_url=f"https://{STORAGE_ACCOUNT}.dfs.core.windows.net",
    credential=credential,
)

file_system_client = service_client.get_file_system_client(FILE_SYSTEM)
directory_client = file_system_client.get_directory_client(TARGET_DIR)


def generate_live_orders(n: int) -> pd.DataFrame:
    rows = []

    for _ in range(n):
        order_id = str(uuid.uuid4())
        customer_id = random.randint(1, 100_000)
        quantity = random.randint(1, 8)

        # Environ 2 % d'anomalies volontaires
        if random.random() < 0.02:
            anomaly = random.choice(
                [
                    "missing_customer",
                    "negative_quantity",
                    "duplicate_candidate",
                    "future_timestamp",
                ]
            )

            if anomaly == "missing_customer":
                customer_id = None

            elif anomaly == "negative_quantity":
                quantity = -random.randint(1, 5)

            elif anomaly == "duplicate_candidate":
                order_id = f"DUP-{random.randint(1, 1000)}"

            elif anomaly == "future_timestamp":
                order_timestamp = (
                    datetime.now()
                    + pd.Timedelta(days=random.randint(1, 5))
                )
            else:
                order_timestamp = datetime.now()
        else:
            order_timestamp = datetime.now()

        rows.append(
            {
                "order_id": order_id,
                "customer_id": customer_id,
                "product_id": random.randint(1, 10_000),
                "store_id": random.randint(1, 250),
                "order_timestamp": order_timestamp,
                "quantity": quantity,
                "unit_price": round(random.uniform(5, 500), 2),
                "discount": random.choice(
                    [0, 0, 0, 0.05, 0.10, 0.20]
                ),
                "payment_method": random.choice(
                    [
                        "card",
                        "paypal",
                        "bank_transfer",
                        "cash",
                    ]
                ),
                "country": random.choice(
                    ["BE", "FR", "NL", "DE", "LU"]
                ),
                "status": random.choice(
                    [
                        "completed",
                        "completed",
                        "completed",
                        "cancelled",
                        "returned",
                    ]
                ),
                "ingestion_timestamp": datetime.now(),
            }
        )

    return pd.DataFrame(rows)


def upload_batch(df: pd.DataFrame) -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    remote_name = f"orders_{timestamp}.parquet"

    buffer = io.BytesIO()

    df.to_parquet(
        buffer,
        index=False,
        engine="pyarrow",
        coerce_timestamps="us",
        allow_truncated_timestamps=True,
    )

    buffer.seek(0)

    file_client = directory_client.get_file_client(remote_name)
    file_client.upload_data(buffer, overwrite=True)

    print(
        f"{datetime.now().isoformat(timespec='seconds')} | "
        f"{remote_name} | "
        f"{len(df):,} rows uploaded"
    )


print(
    f"Starting NorthMart live generator: "
    f"{ROWS_PER_BATCH} orders every {INTERVAL_SECONDS}s"
)

try:
    while True:
        batch = generate_live_orders(ROWS_PER_BATCH)

        # Stabiliser les types avant écriture Parquet
        batch["customer_id"] = batch["customer_id"].astype("Int64")
        batch["product_id"] = batch["product_id"].astype("Int64")
        batch["store_id"] = batch["store_id"].astype("Int64")
        batch["quantity"] = batch["quantity"].astype("Int64")

        upload_batch(batch)

        time.sleep(INTERVAL_SECONDS)

except KeyboardInterrupt:
    print("\nNorthMart live generator stopped.")