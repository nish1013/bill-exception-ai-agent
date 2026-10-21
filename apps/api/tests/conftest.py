from collections.abc import Iterator

import pytest
from django.db import connections

from tests.tenants import NAMES


@pytest.fixture(scope="session")
def django_db_setup(django_test_environment, django_db_blocker) -> Iterator[None]:
    # The app role cannot create a database, so the owner creates and migrates the test database.
    owner = connections["owner"]
    app = connections["default"]
    original_name = owner.settings_dict["NAME"]
    with django_db_blocker.unblock():
        owner.creation.create_test_db(verbosity=0, autoclobber=True, serialize=False)
        app.creation.set_as_test_mirror(owner.settings_dict)
        with owner.cursor() as cursor:
            for tenant_id, name in NAMES.items():
                cursor.execute(
                    "INSERT INTO tenant (id, name, created_at) VALUES (%s, %s, now())",
                    [tenant_id, name],
                )
    yield
    with django_db_blocker.unblock():
        app.close()
        owner.creation.destroy_test_db(original_name, verbosity=0)
