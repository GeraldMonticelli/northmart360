USE CATALOG northmart_dev;
USE SCHEMA silver;

-- ============================================================
-- PERSONS
-- ============================================================

INSERT INTO sem_person VALUES
('P001', 'Alice', 'Martin', DATE '1985-04-12'),
('P002', 'Bob',   'Dupont', DATE '1990-08-23'),
('P003', 'Chloe', 'Lambert', DATE '2008-10-15');


-- ============================================================
-- ORGANIZATIONS
-- ============================================================

INSERT INTO sem_organization VALUES
('O001', 'NorthMart Brussels'),
('O002', 'TechStore Belgium');


-- ============================================================
-- CUSTOMER ROLES
--
-- Alice is currently a customer.
-- Bob was a customer but ceased playing that role.
-- Chloe becomes a customer while still a minor.
-- ============================================================

INSERT INTO sem_customer VALUES
('C001', 'P001', DATE '2024-01-01', NULL),
('C002', 'P002', DATE '2023-01-01', DATE '2025-12-31'),
('C003', 'P003', DATE '2025-01-01', NULL);


-- ============================================================
-- MERCHANT ROLES
-- ============================================================

INSERT INTO sem_merchant VALUES
('M001', 'O001', DATE '2020-01-01', NULL),
('M002', 'O002', DATE '2022-06-01', NULL);


-- ============================================================
-- CARDS
-- ============================================================

INSERT INTO sem_card VALUES
('CARD001', '**** **** **** 1001', 'ACTIVE'),
('CARD002', '**** **** **** 2002', 'ACTIVE');


-- ============================================================
-- CARD HOLDINGS
--
-- CARD001 changes holder over time.
-- This will later be modeled as a relator.
-- ============================================================

INSERT INTO sem_card_holding VALUES
(
    'H001',
    'C002',
    'CARD001',
    TIMESTAMP '2024-01-01 00:00:00',
    TIMESTAMP '2025-12-31 23:59:59'
),
(
    'H002',
    'C001',
    'CARD001',
    TIMESTAMP '2026-01-01 00:00:00',
    NULL
),
(
    'H003',
    'C003',
    'CARD002',
    TIMESTAMP '2025-01-01 00:00:00',
    NULL
);


-- ============================================================
-- TRANSACTIONS
-- ============================================================

INSERT INTO sem_transaction VALUES
(
    'T001',
    'CARD001',
    'M001',
    TIMESTAMP '2025-06-10 14:30:00',
    49.90,
    'EUR'
),
(
    'T002',
    'CARD001',
    'M002',
    TIMESTAMP '2026-03-15 21:14:00',
    899.00,
    'EUR'
),
(
    'T003',
    'CARD002',
    'M002',
    TIMESTAMP '2026-09-01 10:05:00',
    125.50,
    'EUR'
);


-- ============================================================
-- FRAUD ASSESSMENTS
--
-- T002 demonstrates that:
--   Transaction != assessment about transaction
--
-- The ML model first considers it suspicious.
-- A human analyst later confirms it as legitimate.
-- ============================================================

INSERT INTO sem_fraud_assessment VALUES
(
    'A001',
    'T002',
    'ML_MODEL',
    'FRAUD',
    0.9200,
    TIMESTAMP '2026-03-15 21:14:02',
    'fraud_model_v3'
),
(
    'A002',
    'T002',
    'HUMAN_REVIEW',
    'LEGITIMATE',
    NULL,
    TIMESTAMP '2026-03-16 09:30:00',
    NULL
),
(
    'A003',
    'T003',
    'ML_MODEL',
    'LEGITIMATE',
    0.0800,
    TIMESTAMP '2026-09-01 10:05:02',
    'fraud_model_v3'
);