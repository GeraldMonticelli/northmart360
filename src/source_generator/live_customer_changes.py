from datetime import datetime
import io
import random
import time

import pandas as pd
from azure.identity import DefaultAzureCredential
from azure.storage.filedatalake import DataLakeServiceClient


STORAGE_ACCOUNT = "stnorthmartdev"
FILE_SYSTEM = "unity"

HISTORY_DIR = "source/customers/history"
INCOMING_DIR = "source/customers/incoming"

CHANGES_PER_BATCH = 200
INTERVAL_SECONDS = 30

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


credential = DefaultAzureCredential()

service_client = DataLakeServiceClient(
    account_url=f"https://{STORAGE_ACCOUNT}.dfs.core.windows.net",
    credential=credential,
)

file_system_client = service_client.get_file_system_client(FILE_SYSTEM)
incoming_client = file_system_client.get_directory_client(INCOMING_DIR)


def normalize_types(df: pd.DataFrame) -> pd.DataFrame:
    df["customer_id"] = df["customer_id"].astype("Int64")
    df["sequence_number"] = df["sequence_number"].astype("Int64")
    return df


def read_parquet_from_adls(path: str) -> pd.DataFrame:
    file_client = file_system_client.get_file_client(path)
    data = file_client.download_file().readall()
    return pd.read_parquet(io.BytesIO(data))


def load_history() -> pd.DataFrame:
    frames = []

    for path in file_system_client.get_paths(
        path=HISTORY_DIR,
        recursive=False,
    ):
        if path.is_directory or not path.name.endswith(".parquet"):
            continue

        frames.append(read_parquet_from_adls(path.name))

    if not frames:
        raise RuntimeError(
            "No customer history found in ADLS."
        )

    state = pd.concat(frames, ignore_index=True)
    return normalize_types(state)


def apply_existing_cdc(state: pd.DataFrame) -> pd.DataFrame:
    paths = sorted(
        [
            path
            for path in file_system_client.get_paths(
                path=INCOMING_DIR,
                recursive=False,
            )
            if not path.is_directory
            and path.name.endswith(".parquet")
        ],
        key=lambda p: p.name,
    )

    for path in paths:
        changes = read_parquet_from_adls(path.name)

        if changes.empty:
            continue

        changes = normalize_types(changes)

        # On rejoue dans l'ordre CDC
        changes = changes.sort_values(
            ["customer_id", "sequence_number"]
        )

        for _, event in changes.iterrows():
            customer_id = int(event["customer_id"])
            operation = event["operation"]

            mask = state["customer_id"] == customer_id

            if operation == "INSERT":
                if not mask.any():
                    state = pd.concat(
                        [state, pd.DataFrame([event])],
                        ignore_index=True,
                    )

            elif operation == "UPDATE":
                if mask.any():
                    index = state.index[mask][0]

                    for column, value in event.items():
                        state.at[index, column] = value

            elif operation == "DELETE":
                if mask.any():
                    state = state.loc[~mask].copy()

    state = state.reset_index(drop=True)
    return normalize_types(state)


def create_new_customer(customer_id: int) -> dict:
    now = datetime.now()
    city, country = random.choice(CITIES)

    return {
        "customer_id": customer_id,
        "first_name": f"Customer{customer_id}",
        "last_name": "NorthMart",
        "email": f"customer.{customer_id}@northmart.example",
        "city": city,
        "country": country,
        "loyalty_level": "BRONZE",
        "operation": "INSERT",
        "sequence_number": 1,
        "event_timestamp": now,
        "ingestion_timestamp": now,
    }


def create_update(customer: pd.Series) -> dict:
    event = customer.to_dict()

    attribute = random.choice(
        ["city", "loyalty_level", "email"]
    )

    if attribute == "city":
        city, country = random.choice(CITIES)
        event["city"] = city
        event["country"] = country

    elif attribute == "loyalty_level":
        event["loyalty_level"] = random.choice(
            LOYALTY_LEVELS
        )

    else:
        event["email"] = (
            f"customer.{int(customer['customer_id'])}."
            f"{random.randint(1, 9999)}"
            "@northmart.example"
        )

    event["operation"] = "UPDATE"
    event["sequence_number"] = (
        int(customer["sequence_number"]) + 1
    )
    event["event_timestamp"] = datetime.now()
    event["ingestion_timestamp"] = datetime.now()

    return event


def create_delete(customer: pd.Series) -> dict:
    event = customer.to_dict()

    event["operation"] = "DELETE"
    event["sequence_number"] = (
        int(customer["sequence_number"]) + 1
    )
    event["event_timestamp"] = datetime.now()
    event["ingestion_timestamp"] = datetime.now()

    return event


def generate_changes(
    state: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:

    events = []

    next_customer_id = (
        int(state["customer_id"].max()) + 1
        if not state.empty
        else 1
    )

    for _ in range(CHANGES_PER_BATCH):
        action = random.choices(
            ["INSERT", "UPDATE", "DELETE"],
            weights=[10, 80, 10],
            k=1,
        )[0]

        if action == "INSERT":
            event = create_new_customer(
                next_customer_id
            )

            events.append(event)

            state = pd.concat(
                [state, pd.DataFrame([event])],
                ignore_index=True,
            )

            next_customer_id += 1

        elif action == "UPDATE":
            if state.empty:
                continue

            index = random.choice(
                state.index.tolist()
            )

            customer = state.loc[index]
            event = create_update(customer)
            events.append(event)

            for column, value in event.items():
                state.at[index, column] = value

        else:
            if state.empty:
                continue

            index = random.choice(
                state.index.tolist()
            )

            customer = state.loc[index]
            event = create_delete(customer)
            events.append(event)

            state = (
                state
                .drop(index)
                .reset_index(drop=True)
            )

    events_df = normalize_types(
        pd.DataFrame(events)
    )

    state = normalize_types(state)

    return events_df, state


def upload_batch(df: pd.DataFrame) -> None:
    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    remote_name = (
        f"customer_changes_{timestamp}.parquet"
    )

    buffer = io.BytesIO()

    df.to_parquet(
        buffer,
        engine="pyarrow",
        index=False,
        coerce_timestamps="us",
        allow_truncated_timestamps=True,
    )

    buffer.seek(0)

    file_client = incoming_client.get_file_client(
        remote_name
    )

    file_client.upload_data(
        buffer,
        overwrite=True,
    )

    print(
        f"{datetime.now().isoformat(timespec='seconds')} | "
        f"{remote_name} | "
        f"{len(df):,} CDC events"
    )


def main():
    print("Loading initial customer history...")
    state = load_history()

    print(
        f"{len(state):,} initial customers loaded"
    )

    print("Replaying existing CDC events...")
    state = apply_existing_cdc(state)

    print(
        f"{len(state):,} active customers after replay"
    )

    print(
        f"Starting live CDC: "
        f"{CHANGES_PER_BATCH} changes every "
        f"{INTERVAL_SECONDS}s"
    )

    try:
        while True:
            changes, state = generate_changes(state)
            upload_batch(changes)
            time.sleep(INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("\nCustomer CDC generator stopped.")


if __name__ == "__main__":
    main()