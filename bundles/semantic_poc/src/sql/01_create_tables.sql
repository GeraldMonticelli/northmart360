-- ============================================================
-- Semantic POC - Physical model
-- Catalog : northmart_dev
-- Schema  : silver
-- ============================================================

USE CATALOG northmart_dev;
USE SCHEMA silver;


-- ------------------------------------------------------------
-- PERSON
-- ------------------------------------------------------------
CREATE OR REPLACE TABLE sem_person (
    person_id      STRING    NOT NULL,
    first_name     STRING    NOT NULL,
    last_name      STRING    NOT NULL,
    birth_date     DATE      NOT NULL
)
USING DELTA;


-- ------------------------------------------------------------
-- ORGANIZATION
-- ------------------------------------------------------------
CREATE OR REPLACE TABLE sem_organization (
    organization_id STRING   NOT NULL,
    legal_name      STRING   NOT NULL
)
USING DELTA;


-- ------------------------------------------------------------
-- CUSTOMER
-- A Person may play the role of Customer during a period.
-- ------------------------------------------------------------
CREATE OR REPLACE TABLE sem_customer (
    customer_id    STRING    NOT NULL,
    person_id      STRING    NOT NULL,
    valid_from     DATE      NOT NULL,
    valid_to       DATE
)
USING DELTA;


-- ------------------------------------------------------------
-- MERCHANT
-- An Organization may play the role of Merchant during a period.
-- ------------------------------------------------------------
CREATE OR REPLACE TABLE sem_merchant (
    merchant_id       STRING NOT NULL,
    organization_id   STRING NOT NULL,
    valid_from        DATE   NOT NULL,
    valid_to          DATE
)
USING DELTA;


-- ------------------------------------------------------------
-- CARD
-- ------------------------------------------------------------
CREATE OR REPLACE TABLE sem_card (
    card_id         STRING   NOT NULL,
    masked_number   STRING   NOT NULL,
    status          STRING   NOT NULL
)
USING DELTA;


-- ------------------------------------------------------------
-- CARD HOLDING
-- Temporal relationship between a Customer and a Card.
-- ------------------------------------------------------------
CREATE OR REPLACE TABLE sem_card_holding (
    card_holding_id STRING   NOT NULL,
    customer_id     STRING   NOT NULL,
    card_id         STRING   NOT NULL,
    valid_from      TIMESTAMP NOT NULL,
    valid_to        TIMESTAMP
)
USING DELTA;


-- ------------------------------------------------------------
-- TRANSACTION
-- Business event involving a Card and a Merchant.
-- ------------------------------------------------------------
CREATE OR REPLACE TABLE sem_transaction (
    transaction_id STRING         NOT NULL,
    card_id        STRING         NOT NULL,
    merchant_id    STRING         NOT NULL,
    event_time     TIMESTAMP      NOT NULL,
    amount         DECIMAL(12,2)  NOT NULL,
    currency       STRING         NOT NULL
)
USING DELTA;


-- ------------------------------------------------------------
-- FRAUD ASSESSMENT
-- Assessment about a Transaction.
-- Kept separate from the Transaction itself intentionally.
-- ------------------------------------------------------------
CREATE OR REPLACE TABLE sem_fraud_assessment (
    assessment_id    STRING         NOT NULL,
    transaction_id   STRING         NOT NULL,
    assessment_type  STRING         NOT NULL,
    result           STRING         NOT NULL,
    probability      DECIMAL(5,4),
    assessed_at      TIMESTAMP      NOT NULL,
    model_version    STRING
)
USING DELTA;