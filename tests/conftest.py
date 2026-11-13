import pytest

from cuadra.ingesta import cargar


@pytest.fixture(scope="session")
def datos():
    return cargar()
