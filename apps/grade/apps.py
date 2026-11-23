from django.apps import AppConfig


class GradeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.grade"
    label = "grade"
    verbose_name = "Grade horária"
