from django.apps import AppConfig


class CredentialappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'credentialapp'

    def ready(self):
        import credentialapp.signals
