"""Serializers da app accounts."""
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Usuario


class UsuarioTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Inclui `escola_id` e `perfil` no payload do JWT.

    Permite que o frontend leia o escopo de tenancy e o perfil de acesso
    direto do token, sem precisar fazer GET extra em `/usuarios/me/` após
    o login.

    Trade-off conhecido: se admin trocar `escola` ou `perfil` do usuário,
    o JWT antigo continua refletindo o estado anterior até expirar
    (ACCESS_TOKEN_LIFETIME = 1h). Para invalidação imediata, seria
    necessário token blacklist server-side — fora do escopo do MVP.
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["escola_id"] = user.escola_id
        token["perfil"] = user.perfil
        return token


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
