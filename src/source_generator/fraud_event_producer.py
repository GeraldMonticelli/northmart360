import json
import os
import random
import time
import uuid
from datetime import datetime, timezone

from confluent_kafka import Producer


BOOTSTRAP_SERVERS = os.environ["KAFKA_BOOTSTRAP_SERVERS"]
TOPIC = os.environ["KAFKA_TOPIC"]
CONNECTION_STRING = os.environ["EVENTHUB_CONNECTION_STRING"]


producer = Producer(
    {
        "bootstrap.servers": BOOTSTRAP_SERVERS,
        "security.protocol": "SASL_SSL",
        "sasl.mechanism": "PLAIN",
        "sasl.username": "$ConnectionString",
        "sasl.password": CONNECTION_STRING,
    }
)


COUNTRIES = ["BE", "FR", "NL", "DE", "LU"]
MERCHANT_CATEGORIES = [
    "GROCERY",
    "RESTAURANT",
    "FUEL",
    "ELECTRONICS",
    "TRAVEL",
    "ECOMMERCE",
]

CHANNELS = [
    "POS",
    "ECOMMERCE",
    "MOBILE",
    "ATM",
]


def delivery_report(err, msg):
    if err is not None:
        print(f"FAILED: {err}")
        return

    print(
        f"SENT "
        f"partition={msg.partition()} "
        f"offset={msg.offset()}"
    )


def generate_normal_transaction():
    customer_id = random.randint(1, 10_000)
    card_id = random.randint(1, 15_000)

    return {
        "transaction_id": str(uuid.uuid4()),
        "customer_id": f"C-{customer_id:06d}",
        "card_id": f"CARD-{card_id:06d}",
        "event_time": datetime.now(timezone.utc).isoformat(),
        "amount": round(random.uniform(5, 300), 2),
        "currency": "EUR",
        "country": random.choice(COUNTRIES),
        "merchant_id": f"M-{random.randint(1, 5000):05d}",
        "merchant_category": random.choice(MERCHANT_CATEGORIES),
        "channel": random.choice(CHANNELS),
        "device_id": f"DEV-{random.randint(1, 20000):06d}",
        "fraud_scenario": None,
    }


def generate_suspicious_transaction():
    transaction = generate_normal_transaction()

    scenario = random.choice(
        [
            "HIGH_AMOUNT",
            "FOREIGN_TRANSACTION",
            "NEW_DEVICE_HIGH_AMOUNT",
        ]
    )

    if scenario == "HIGH_AMOUNT":
        transaction["amount"] = round(
            random.uniform(2000, 8000),
            2,
        )

    elif scenario == "FOREIGN_TRANSACTION":
        transaction["country"] = random.choice(
            ["RU", "CN", "BR", "SG"]
        )

        transaction["amount"] = round(
            random.uniform(500, 4000),
            2,
        )

    elif scenario == "NEW_DEVICE_HIGH_AMOUNT":
        transaction["device_id"] = (
            f"NEW-DEV-{uuid.uuid4().hex[:8]}"
        )

        transaction["amount"] = round(
            random.uniform(1500, 6000),
            2,
        )

    transaction["fraud_scenario"] = scenario

    return transaction


def main():
    print("Starting NorthMart fraud Kafka producer")
    print(f"Broker: {BOOTSTRAP_SERVERS}")
    print(f"Topic : {TOPIC}")

    while True:
        # Environ 5 % d'événements suspects
        if random.random() < 0.05:
            event = generate_suspicious_transaction()
        else:
            event = generate_normal_transaction()

        payload = json.dumps(event).encode("utf-8")

        producer.produce(
            topic=TOPIC,
            key=event["card_id"].encode("utf-8"),
            value=payload,
            callback=delivery_report,
        )

        # Permet à librdkafka de traiter les callbacks
        producer.poll(0)

        print(
            f"{event['event_time']} | "
            f"{event['transaction_id']} | "
            f"{event['card_id']} | "
            f"{event['amount']} EUR | "
            f"{event['country']} | "
            f"{event['fraud_scenario'] or 'NORMAL'}"
        )

        time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopping producer...")
        producer.flush(10)
