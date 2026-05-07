"""Serializers da app accounts."""
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Usuario


class UsuarioSerializer(serializers.ModelSerializer):
    """Serializa Usuario para respostas da API."""

    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = Usuario
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "perfil",
            "is_active",
            "password",
        ]
        read_only_fields = ["id"]

    def validate_password(self, value: str) -> str:
        """Aplica os validadores configurados em AUTH_PASSWORD_VALIDATORS."""
        validate_password(value)
        return value

    def create(self, validated_data: dict) -> Usuario:
        password = validated_data.pop("password", None)
        usuario = Usuario(**validated_data)
        if password:
            usuario.set_password(password)
        usuario.save()
        return usuario

    def update(self, instance: Usuario, validated_data: dict) -> Usuario:
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance
