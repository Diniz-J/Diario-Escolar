"""Serializers da app accounts."""
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Usuario


class UsuarioTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Inclui claims customizados no payload do JWT.

    Claims expostos:
    - `escola_id`, `perfil` — escopo de tenancy e perfil de acesso.
    - `username`, `first_name`, `last_name` — identificação humana, para
      o frontend exibir "Olá, Fulano" sem precisar de request extra.

    Trade-off conhecido: se admin trocar `escola`/`perfil`/`nome` do
    usuário, os JWTs já emitidos continuam refletindo o estado anterior.
    Como `TokenRefreshView` (SimpleJWT 5.x) propaga claims do refresh
    para o novo access, a janela real de staleness é o
    `REFRESH_TOKEN_LIFETIME` (7 dias por default), não o
    `ACCESS_TOKEN_LIFETIME` (1h). Invalidação imediata exige blacklist
    server-side — fora do escopo do MVP.
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["escola_id"] = user.escola_id
        token["perfil"] = user.perfil
        token["username"] = user.username
        token["first_name"] = user.first_name
        token["last_name"] = user.last_name
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
            # `escola` precisa ser editável para que o frontend consiga
            # criar Professor (ProfessorSerializer exige que o usuário
            # vinculado pertença à mesma escola do professor).
            "escola",
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
