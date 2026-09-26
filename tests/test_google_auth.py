"""Login OAuth compartilhado (calendário + Gmail), sem Google de verdade.

As duas conferências que a biblioteca não faz (ver o docstring de `lifeos/google_auth.py`) são as
que decidem acesso: token salvo para outro escopo não pode passar como válido, e login com a
permissão desmarcada não pode virar token gravado.
"""

import json
import stat

import pytest

from lifeos import google_auth

GMAIL = ["https://www.googleapis.com/auth/gmail.readonly"]
CALENDARIO = ["https://www.googleapis.com/auth/calendar"]


class _Creds:
    def __init__(self, scopes, *, valid=True, expired=False, refresh_token="r", granted=None):
        self.scopes = list(scopes)
        self.valid = valid
        self.expired = expired
        self.refresh_token = refresh_token
        self.granted_scopes = granted
        self.renovado = False

    def refresh(self, _request):
        if self.refresh_token == "revogado":
            raise google_auth.RefreshError("invalid_grant: Token has been expired or revoked.")
        self.valid, self.expired, self.renovado = True, False, True

    def to_json(self):
        return json.dumps({"scopes": self.scopes, "token": "t", "refresh_token": "r"})


@pytest.fixture()
def google(monkeypatch, tmp_path):
    """Troca carga do token, fluxo de login e `build` por falsos que registram o que aconteceu."""
    estado = {"logins": 0, "carregado": None, "concedidos": None, "build": []}
    segredo = tmp_path / "client_secret.json"
    segredo.write_text("{}")
    monkeypatch.setattr(google_auth, "GOOGLE_CREDENTIALS_PATH", segredo)

    def carregar(caminho, scopes):
        return estado["carregado"] or _Creds(scopes)

    class _Fluxo:
        def __init__(self, scopes):
            self.scopes = scopes

        def run_local_server(self, port):
            estado["logins"] += 1
            concedidos = estado["concedidos"]
            return _Creds(self.scopes, granted=self.scopes if concedidos is None else concedidos)

    monkeypatch.setattr(
        google_auth.Credentials, "from_authorized_user_file", staticmethod(carregar)
    )
    monkeypatch.setattr(
        google_auth.InstalledAppFlow,
        "from_client_secrets_file",
        staticmethod(lambda _caminho, scopes: _Fluxo(scopes)),
    )
    monkeypatch.setattr(google_auth, "build", lambda *a, **k: estado["build"].append(a) or "svc")
    estado["token"] = tmp_path / "token.json"
    estado["segredo"] = segredo
    return estado


def _salvar_token(caminho, scopes, modo=0o600):
    caminho.write_text(json.dumps({"scopes": scopes, "token": "t"}))
    caminho.chmod(modo)


def test_token_valido_do_mesmo_escopo_nao_abre_login(google):
    _salvar_token(google["token"], GMAIL)
    assert google_auth.servico("gmail", "v1", GMAIL, google["token"]) == "svc"
    assert google["logins"] == 0
    assert google["build"] == [("gmail", "v1")]


def test_token_de_outro_escopo_abre_login_em_vez_de_passar_como_valido(google):
    """O caso que a biblioteca deixaria passar: token do calendário lido para o Gmail."""
    _salvar_token(google["token"], CALENDARIO)
    google_auth.credenciais(GMAIL, google["token"])
    assert google["logins"] == 1
    assert json.loads(google["token"].read_text())["scopes"] == GMAIL


def test_token_expirado_e_renovado_sem_login(google):
    _salvar_token(google["token"], GMAIL)
    google["carregado"] = _Creds(GMAIL, valid=False, expired=True)
    creds = google_auth.credenciais(GMAIL, google["token"])
    assert creds.renovado and google["logins"] == 0


def test_renovacao_recusada_vira_login_novo_e_nao_beco_sem_saida(google):
    """Token revogado no Google: antes, toda tentativa (inclusive `--login`) renovava o mesmo token
    morto e falhava igual, e o único conserto era apagar o arquivo à mão."""
    _salvar_token(google["token"], GMAIL)
    google["carregado"] = _Creds(GMAIL, valid=False, expired=True, refresh_token="revogado")
    google_auth.credenciais(GMAIL, google["token"])
    assert google["logins"] == 1


def test_permissao_desmarcada_no_login_falha_alto_e_nao_grava_token(google):
    google["concedidos"] = ["openid"]
    with pytest.raises(google_auth.PermissaoNaoConcedida, match="gmail.readonly"):
        google_auth.credenciais(GMAIL, google["token"])
    assert not google["token"].exists()


def test_sem_client_secret_explica_onde_devia_estar(google):
    google["segredo"].unlink()
    with pytest.raises(FileNotFoundError, match="docs/fontes/google-calendar-api.md"):
        google_auth.credenciais(GMAIL, google["token"])
    assert google["logins"] == 0


@pytest.mark.parametrize("conteudo", ["não é json", "[]", '{"scopes": null}'])
def test_token_ilegivel_vira_login_novo(google, conteudo):
    google["token"].write_text(conteudo)
    google_auth.credenciais(GMAIL, google["token"])
    assert google["logins"] == 1


def test_token_gravado_so_legivel_pelo_dono(google):
    """Refresh token dá acesso à conta: 600, inclusive quando o arquivo já existia com 644."""
    _salvar_token(google["token"], CALENDARIO, modo=0o644)
    google_auth.credenciais(GMAIL, google["token"])
    assert stat.S_IMODE(google["token"].stat().st_mode) == 0o600


def test_escopos_em_string_unica_tambem_sao_lidos(google):
    google["token"].write_text(json.dumps({"scopes": " ".join(GMAIL + CALENDARIO)}))
    google_auth.credenciais(GMAIL, google["token"])
    assert google["logins"] == 0
