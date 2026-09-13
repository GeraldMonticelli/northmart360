import pytest
from databricks.connect import DatabricksSession


@pytest.fixture(scope="session")
def spark():
    session = (
        DatabricksSession.builder
        .serverless()
        .getOrCreate()
    )

    yield session