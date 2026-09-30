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


# --- na nuvem (Sessão 10b): o token vem do segredo, renova em memória, e o login nunca abre ------

SCOPES_CAL = ["https://www.googleapis.com/auth/calendar"]
_TOKEN_DA_AGENDA = {
    "token": "velho",
    "refresh_token": "r",
    "client_id": "c",
    "client_secret": "s",
    "token_uri": "https://oauth2.googleapis.com/token",
    "scopes": ["https://www.googleapis.com/auth/calendar"],
    "expiry": "2026-09-19T21:26:07Z",
}


@pytest.fixture
def na_nuvem(monkeypatch):
    from lifeos import config

    monkeypatch.setattr(config, "STORE", "firestore")
    monkeypatch.setattr(google_auth, "_NA_NUVEM", {})
    monkeypatch.setattr(config, "agenda_token", lambda: json.dumps(_TOKEN_DA_AGENDA))
    monkeypatch.setattr(google_auth, "InstalledAppFlow", None)  # abrir login quebraria aqui
    monkeypatch.setattr(google_auth, "_gravar_token", _nunca)
    renovou = []

    def refresh(self, _request):
        renovou.append(1)
        self.token = "novo"
        self.expiry = None  # sem validade conhecida: `valid` fica verdadeiro

    monkeypatch.setattr(google_auth.Credentials, "refresh", refresh)
    return renovou


def _nunca(*_a, **_k):
    raise AssertionError("na nuvem nada é gravado nem abre login")


def test_na_nuvem_o_servico_usa_o_segredo_e_nunca_o_login(na_nuvem, monkeypatch):
    from lifeos import config

    usadas = []
    monkeypatch.setattr(google_auth, "build", lambda *_a, credentials: usadas.append(credentials))
    google_auth.servico("calendar", "v3", SCOPES_CAL, config.GOOGLE_TOKEN_PATH)
    google_auth.servico("calendar", "v3", SCOPES_CAL, config.GOOGLE_TOKEN_PATH)
    assert usadas[0].token == "novo" and usadas[0] is usadas[1]  # um objeto por processo
    assert na_nuvem == [1]  # renovou uma vez, em memória


_TOKEN_DO_GMAIL = {**_TOKEN_DA_AGENDA, "scopes": ["https://www.googleapis.com/auth/gmail.modify"]}
SCOPES_GMAIL = ["https://www.googleapis.com/auth/gmail.modify"]


def test_na_nuvem_o_gmail_usa_o_segredo_dele(na_nuvem, monkeypatch, tmp_path):
    """Sessão 10c: cada token vem do seu segredo e renova à parte; outro caminho é recusado."""
    from lifeos import config

    monkeypatch.setattr(config, "gmail_token", lambda: json.dumps(_TOKEN_DO_GMAIL))
    gmail = google_auth.credenciais_da_nuvem(SCOPES_GMAIL, config.GMAIL_TOKEN_PATH)
    agenda = google_auth.credenciais_da_nuvem(SCOPES_CAL, config.GOOGLE_TOKEN_PATH)
    assert gmail is not agenda and set(google_auth._NA_NUVEM) == {"gmail", "agenda"}
    assert google_auth.credenciais_da_nuvem(SCOPES_GMAIL, config.GMAIL_TOKEN_PATH) is gmail
    with pytest.raises(google_auth.TokenDaNuvemRecusado, match="do Gmail"):
        google_auth._NA_NUVEM.clear()
        google_auth.credenciais_da_nuvem(SCOPES_CAL, config.GMAIL_TOKEN_PATH)
    with pytest.raises(RuntimeError, match="agenda e do Gmail"):
        google_auth.credenciais_da_nuvem(SCOPES_GMAIL, tmp_path / "outro.json")


def test_na_nuvem_gmail_recusado_manda_subir_do_mac(na_nuvem, monkeypatch):
    from google.auth.exceptions import RefreshError

    from lifeos import config

    def recusa(self, _request):
        raise RefreshError("invalid_grant")

    monkeypatch.setattr(config, "gmail_token", lambda: json.dumps(_TOKEN_DO_GMAIL))
    monkeypatch.setattr(google_auth.Credentials, "refresh", recusa)
    with pytest.raises(google_auth.TokenDaNuvemRecusado) as erro:
        google_auth.credenciais_da_nuvem(SCOPES_GMAIL, config.GMAIL_TOKEN_PATH)
    assert "segredo viking-gmail" in str(erro.value) and "no Mac" in str(erro.value)


def test_na_nuvem_escopo_que_falta_erra_alto(na_nuvem):
    from lifeos import config

    with pytest.raises(google_auth.TokenDaNuvemRecusado, match="permissão"):
        google_auth.credenciais_da_nuvem(
            ["https://www.googleapis.com/auth/gmail.modify"], config.GOOGLE_TOKEN_PATH
        )


def test_na_nuvem_renovacao_recusada_erra_alto_e_nao_guarda(na_nuvem, monkeypatch):
    from google.auth.exceptions import RefreshError

    from lifeos import config

    def recusa(self, _request):
        raise RefreshError("invalid_grant")

    monkeypatch.setattr(google_auth.Credentials, "refresh", recusa)
    with pytest.raises(google_auth.TokenDaNuvemRecusado, match="suba um novo"):
        google_auth.credenciais_da_nuvem(SCOPES_CAL, config.GOOGLE_TOKEN_PATH)
    assert google_auth._NA_NUVEM == {}


def test_segredo_e_lido_uma_vez_e_vazio_erra_sem_mostrar(monkeypatch, tmp_path):
    from lifeos import config

    monkeypatch.setattr(config, "_SEGREDOS", {})
    chave = tmp_path / "chave"
    chave.write_text("AIza-de-teste\n")
    monkeypatch.setattr(config, "GEMINI_CHAVE_ARQUIVO", str(chave))
    assert config.gemini_chave() == "AIza-de-teste"
    chave.unlink()  # a segunda leitura não vai ao volume (cada leitura é um acesso cobrado)
    assert config.gemini_chave() == "AIza-de-teste"
    vazio = tmp_path / "vazio"
    vazio.write_text("\n")
    monkeypatch.setattr(config, "GEMINI_CHAVE_ARQUIVO", str(vazio))
    with pytest.raises(RuntimeError, match="vazio"):
        config.gemini_chave()
