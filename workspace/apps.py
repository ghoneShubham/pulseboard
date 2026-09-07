from django.apps import AppConfig


class WorkspaceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "workspace"

    def ready(self):
        # Signals yahin import karo - module import time pe nahi, warna
        # app registry ready nahi hoti aur circular imports aate hain.
        from . import signals  # noqa: F401
