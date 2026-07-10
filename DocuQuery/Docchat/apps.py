from django.apps import AppConfig


class DocchatConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Docchat'

    def ready(self):
        import Docchat.signals