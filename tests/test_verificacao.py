import asyncio

import pytest

from texto_audio import verificacao
from texto_audio.motores import ErroSintese, VozRecusada


class Motor:
    def __init__(self, erro=None):
        self.erro = erro

    async def sintetizar(self, texto, destino, voz, velocidade):
        if self.erro:
            raise self.erro
        destino.write_bytes(b"mp3")


def diagnosticar(monkeypatch, motor, publicada, instalada="7.3.1"):
    async def consultar():
        return publicada

    monkeypatch.setattr(verificacao, "versao_publicada", consultar)
    monkeypatch.setattr(verificacao.edge_tts, "__version__", instalada)
    return asyncio.run(verificacao.verificar(motor))


@pytest.mark.parametrize("motor, publicada, voz, nova, trecho", [
    (Motor(), "7.3.1", "ok", False, "versão mais recente"),
    (Motor(), "7.10.0", "ok", True, "próxima reconstrução"),
    (Motor(VozRecusada()), "7.4.0", "recusada", True, "Já existe correção: a edge-tts 7.4.0"),
    (Motor(VozRecusada()), "7.3.1", "recusada", False, "Ainda não há correção"),
    (Motor(ErroSintese("sem rede")), None, "falhou", False, "não consegui consultar"),
])
def test_diagnostico_combina_voz_e_versao(monkeypatch, motor, publicada, voz,
                                          nova, trecho):
    r = diagnosticar(monkeypatch, motor, publicada)
    assert r["voz"] == voz
    assert r["atualizacao_disponivel"] is nova
    assert r["instalada"] == "7.3.1"
    assert trecho in r["mensagem"]


def test_versao_antiga_no_pypi_nao_conta_como_atualizacao(monkeypatch):
    r = diagnosticar(monkeypatch, Motor(), "7.2.8")
    assert r["atualizacao_disponivel"] is False
