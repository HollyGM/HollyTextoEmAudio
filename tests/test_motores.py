import asyncio

import pytest

from texto_audio import motores
from texto_audio.motores import ErroSintese, MotorEdge, VozRecusada


def test_tentativas_invalidas_rejeitadas():
    with pytest.raises(ValueError, match="pelo menos uma"):
        MotorEdge(tentativas=0)


def test_erro_de_sintese_remove_arquivo_parcial_sem_esperar_apos_ultima_tentativa(
        tmp_path, monkeypatch):
    esperas = []

    async def esperar(segundos):
        esperas.append(segundos)

    class Comunicacao:
        def __init__(self, *args, **kwargs):
            pass

        async def save(self, destino):
            from pathlib import Path
            Path(destino).write_bytes(b"audio incompleto")
            raise ConnectionError("sem rede")

    monkeypatch.setattr(motores.edge_tts, "Communicate", Comunicacao)
    monkeypatch.setattr(motores.asyncio, "sleep", esperar)
    destino = tmp_path / "audio.mp3"
    with pytest.raises(ErroSintese, match="após 2 tentativas"):
        asyncio.run(MotorEdge(tentativas=2).sintetizar("Olá.", destino, "voz", 0))
    assert not destino.exists()
    assert esperas == [1.5]


def test_recusa_da_microsoft_nao_repete_e_explica(tmp_path, monkeypatch):
    import aiohttp

    chamadas = []

    class Comunicacao:
        def __init__(self, *args, **kwargs):
            chamadas.append(1)

        async def save(self, destino):
            raise aiohttp.WSServerHandshakeError(None, (), status=403,
                                                 message="Invalid response status")

    monkeypatch.setattr(motores.edge_tts, "Communicate", Comunicacao)
    with pytest.raises(VozRecusada, match="erro 403.*Verificar serviço de voz"):
        asyncio.run(MotorEdge(tentativas=4).sintetizar(
            "Olá.", tmp_path / "audio.mp3", "voz", 0))
    assert chamadas == [1]
