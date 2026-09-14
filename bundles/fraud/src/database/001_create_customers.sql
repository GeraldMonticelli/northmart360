CREATE TABLE dbo.customers
(
    customer_id      BIGINT         NOT NULL,
    first_name       NVARCHAR(100)  NOT NULL,
    last_name        NVARCHAR(100)  NOT NULL,
    email            NVARCHAR(255)  NULL,
    city             NVARCHAR(100)  NULL,
    country          CHAR(2)        NULL,
    loyalty_level    VARCHAR(20)    NULL,
    created_at       DATETIME2(6)   NOT NULL
        CONSTRAINT DF_customers_created_at DEFAULT SYSUTCDATETIME(),
    updated_at       DATETIME2(6)   NOT NULL
        CONSTRAINT DF_customers_updated_at DEFAULT SYSUTCDATETIME(),

    CONSTRAINT PK_customers
        PRIMARY KEY (customer_id)
);