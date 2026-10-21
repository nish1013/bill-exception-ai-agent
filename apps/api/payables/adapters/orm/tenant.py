import uuid

from django.db import models


class Tenant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "payables"
        db_table = "tenant"
