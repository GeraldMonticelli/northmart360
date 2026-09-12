from datetime import datetime
from pathlib import Path
import random

import pandas as pd
from faker import Faker
from azure.identity import DefaultAzureCredential
from azure.storage.filedatalake import DataLakeServiceClient


STORAGE_ACCOUNT = "stnorthmartdev"
FILE_SYSTEM = "unity"
TARGET_DIR = "source/customers/history"

TOTAL_CUSTOMERS = 100_000
ROWS_PER_FILE = 20_000

# État local utilisé ensuite par le générateur CDC live
STATE_FILE = Path("data/state/customers_state.parquet")

fake = Faker(["fr_BE", "nl_BE"])


credential = DefaultAzureCredential()

service_client = DataLakeServiceClient(
    account_url=f"https://{STORAGE_ACCOUNT}.dfs.core.windows.net",
    credential=credential,
)

file_system_client = service_client.get_file_system_client(FILE_SYSTEM)
directory_client = file_system_client.get_directory_client(TARGET_DIR)


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

LOYALTY_LEVELS = [
    "BRONZE",
    "SILVER",
    "GOLD",
]


def generate_customer(customer_id: int) -> dict:
    first_name = fake.first_name()
    last_name = fake.last_name()

    city, country = random.choice(CITIES)

    email = (
        f"{first_name}.{last_name}.{customer_id}"
        "@northmart.example"
    ).lower().replace(" ", "")

    now = datetime.now()

    return {
        "customer_id": customer_id,
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "city": city,
        "country": country,
        "loyalty_level": random.choices(
            LOYALTY_LEVELS,
            weights=[60, 30, 10],
            k=1,
        )[0],

        # CDC metadata
        "operation": "INSERT",
        "sequence_number": 1,
        "event_timestamp": now,
        "ingestion_timestamp": now,
    }


def normalize_types(df: pd.DataFrame) -> pd.DataFrame:
    df["customer_id"] = df["customer_id"].astype("Int64")
    df["sequence_number"] = df["sequence_number"].astype("Int64")

    return df


def upload_parquet(
    df: pd.DataFrame,
    remote_name: str,
) -> None:

    local_file = f"/tmp/{remote_name}"

    df.to_parquet(
        local_file,
        engine="pyarrow",
        index=False,
        coerce_timestamps="us",
        allow_truncated_timestamps=True,
    )

    file_client = directory_client.get_file_client(remote_name)

    with open(local_file, "rb") as data:
        file_client.upload_data(
            data,
            overwrite=True,
        )


def main():

    all_customers = []

    for customer_id in range(1, TOTAL_CUSTOMERS + 1):

        customer = generate_customer(customer_id)
        all_customers.append(customer)

        if customer_id % ROWS_PER_FILE == 0:

            batch_number = customer_id // ROWS_PER_FILE

            batch = pd.DataFrame(
                all_customers[-ROWS_PER_FILE:]
            )

            batch = normalize_types(batch)

            remote_name = (
                f"customers_{batch_number:03d}.parquet"
            )

            upload_parquet(
                batch,
                remote_name,
            )

            print(
                f"Uploaded {remote_name}: "
                f"{len(batch):,} customers"
            )

    # État courant local pour le générateur CDC
    state_df = pd.DataFrame(all_customers)
    state_df = normalize_types(state_df)

    STATE_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    state_df.to_parquet(
        STATE_FILE,
        engine="pyarrow",
        index=False,
        coerce_timestamps="us",
        allow_truncated_timestamps=True,
    )

    print()
    print(
        f"Bootstrap complete: "
        f"{len(state_df):,} customers"
    )

    print(
        f"Local CDC state written to: {STATE_FILE}"
    )


if __name__ == "__main__":
    main()