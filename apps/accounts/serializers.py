"""Serializers da app accounts."""
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.common.permissions import eh_admin_global

from .models import Usuario


class PasswordResetRequestSerializer(serializers.Serializer):
    """Body do POST /auth/password/reset/request/.

    Recebe apenas o `username` — o backend resolve o email cadastrado.
    Esta escolha é deliberada (vs. receber email diretamente): impede que
    alguém com o username de um colega aponte o reset pro próprio email.
    """

    username = serializers.CharField(max_length=150)


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Body do POST /auth/password/reset/confirm/."""

    token = serializers.CharField(max_length=128)
    new_password = serializers.CharField(max_length=128, write_only=True)

    def validate_new_password(self, value: str) -> str:
        validate_password(value)
        return value


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
    # Email é a chave do fluxo de redefinição de senha — obrigatório no
    # cadastro (sobrescreve o `blank=True` herdado do AbstractUser).
    email = serializers.EmailField(required=True, allow_blank=False)

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

    # Campos que só o admin global grava, em criação ou atualização.
    #
    # `password` é o vetor de takeover silencioso: quem define a senha de
    # um terceiro entra na conta dele sem passar por email nem token. A
    # direção tem o caminho certo, que é a action `enviar-reset-senha` —
    # o link vai pro email do próprio alvo e quem dispara nunca vê a
    # senha. `escola` move o usuário de tenant, e numa instalação
    # multi-escola isso é a fronteira do isolamento.
    #
    # `perfil` e `is_active` **saíram** desta lista (out/2026, decisão do
    # Diniz): a direção precisa cadastrar a própria secretaria e cortar o
    # acesso de quem saiu da escola sem depender do `/admin/`. Os dois
    # ganharam regra própria abaixo em vez de liberação cega — ver
    # `_validar_perfil_alvo` e `_validar_autoalteracao`.
    _CAMPOS_SO_ADMIN = ("password", "escola")

    def validate_password(self, value: str) -> str:
        """Aplica os validadores configurados em AUTH_PASSWORD_VALIDATORS."""
        validate_password(value)
        return value

    def _validar_perfil_alvo(self, attrs: dict) -> None:
        """`admin` é a fronteira: nível-direção não cria nem promove a ela.

        Secretaria, coordenador e diretor operam no mesmo nível (são
        aliases em `apps/common/permissions.py`), então uma secretaria
        cadastrar uma diretora é movimento **lateral** — ela já tinha
        escrita total sobre os dados daquela escola. `admin` não: dá
        bypass em toda permission class e alcança as outras escolas.
        """
        perfil = attrs.get("perfil")
        if perfil is not None and perfil == Usuario.Perfil.ADMIN:
            raise serializers.ValidationError(
                {
                    "perfil": (
                        "Apenas um administrador pode criar ou promover "
                        "conta com este perfil."
                    )
                }
            )

    def _validar_autoalteracao(self, attrs: dict, usuario) -> None:
        """Ninguém muda o próprio perfil nem se desativa.

        O auto-tranco é o motivo real: uma diretora que se desativa fica
        de fora, e **dentro da escola não sobra quem a destranque** —
        viraria chamado pro admin global. Mudar o próprio perfil é
        higiene: não é escalada (o nível é o mesmo), mas não existe caso
        de uso e esconde erro de clique.
        """
        if self.instance is None or self.instance.pk != usuario.pk:
            return
        if "perfil" in attrs and attrs["perfil"] != self.instance.perfil:
            raise serializers.ValidationError(
                {"perfil": "Você não pode alterar o seu próprio perfil."}
            )
        if attrs.get("is_active") is False:
            raise serializers.ValidationError(
                {"is_active": "Você não pode desativar a sua própria conta."}
            )

    def validate(self, attrs: dict) -> dict:
        """Bloqueia escalada de privilégio por quem não é admin global.

        O ViewSet é liberado pra `IsAdminOrDiretor`, que inclui
        `secretaria` e `coordenador`. Sem estas regras, qualquer conta de
        nível-diretor conseguia:

        - `PATCH {"perfil": "admin"}` em si mesma e virar admin global
          (bypass em todas as permission classes);
        - `PATCH {"password": ...}` em qualquer conta, inclusive a do
          admin, tomando a conta sem passar por email nem token;
        - criar uma conta `admin` nova pela porta de trás;
        - mover um usuário pra outra escola.

        Regra hoje: `password` e `escola` são de admin global, em criação
        e em atualização. `perfil` e `is_active` a direção mexe, com dois
        limites — nunca pra/de `admin` (`_validar_perfil_alvo`) e nunca na
        própria conta (`_validar_autoalteracao`).

        Pra redefinir a senha de um terceiro, a direção tem o caminho
        correto: a action `enviar-reset-senha`, que manda o link pro email
        do próprio alvo — quem dispara nunca vê nem define a senha.

        Falta uma peça aqui que **não** é deste arquivo: quem é o alvo. O
        serializer não barra operar sobre a conta do admin global, porque
        o alvo é assunto da view (`_checar_alvo_privilegiado`), que roda
        antes do save. Separar assim evita duas cópias da mesma regra com
        vocabulário diferente.
        """
        request = self.context.get("request")
        if request is None or not request.user.is_authenticated:
            return attrs
        if eh_admin_global(request.user):
            return attrs

        usuario = request.user

        self._validar_perfil_alvo(attrs)

        if self.instance is not None:
            # Só na ATUALIZAÇÃO. Na criação os dois são legítimos: a conta
            # nasce agora, então definir a senha dela não toma nada de
            # ninguém, e a `escola` é obrigatória pro cadastro de
            # professor — presa à do autor pelo guard logo abaixo. É o
            # update que os torna perigosos: aí existe um dono do outro
            # lado, e trocar a escola dele é pulo de tenant.
            proibidos = sorted(
                campo for campo in self._CAMPOS_SO_ADMIN if campo in attrs
            )
            if proibidos:
                raise serializers.ValidationError(
                    {
                        campo: (
                            "Apenas um administrador pode alterar este campo."
                        )
                        for campo in proibidos
                    }
                )
            self._validar_autoalteracao(attrs, usuario)
            return attrs

        # Criação.
        escola = attrs.get("escola")
        if not usuario.escola_id:
            raise serializers.ValidationError(
                {
                    "escola": (
                        "Seu usuário não está vinculado a uma escola, então "
                        "não é possível criar usuários."
                    )
                }
            )
        if escola is not None and escola.id != usuario.escola_id:
            raise serializers.ValidationError(
                {"escola": "Você só pode criar usuários na sua própria escola."}
            )
        return attrs

    def create(self, validated_data: dict) -> Usuario:
        password = validated_data.pop("password", None)
        usuario = Usuario(**validated_data)
        if password:
            usuario.set_password(password)
        else:
            # Sem isto o hash fica em string vazia, que é um estado
            # ambíguo: não casa com senha nenhuma, mas também não é o
            # marcador de "inutilizável" que o `has_usable_password()`
            # entende. A tela de usuários cria conta justamente sem
            # senha (o acesso chega pelo link de redefinição), então
            # este ramo deixou de ser teórico.
            usuario.set_unusable_password()
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
