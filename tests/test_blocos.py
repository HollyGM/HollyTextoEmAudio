from texto_audio.blocos import dividir


def test_um_bloco_por_paragrafo_curto_com_pausa():
    blocos = dividir("Primeiro.\nSegundo.", pausa_paragrafo_ms=700)
    assert [b.texto for b in blocos] == ["Primeiro.", "Segundo."]
    assert blocos[0].pausa_ms == int(700 * 1.4)      # parágrafo curto = título
    assert blocos[-1].pausa_ms == 0                  # sem silêncio no fim


def test_paragrafo_longo_e_dividido_em_frases_sem_passar_do_limite():
    frase = "Esta é uma frase de tamanho razoável para o teste. "
    paragrafo = (frase * 40).strip()
    blocos = dividir(paragrafo, limite=300)
    assert len(blocos) > 1
    assert all(len(b.texto) <= 300 for b in blocos)
    assert " ".join(b.texto for b in blocos) == paragrafo      # nada se perde
    assert all(b.pausa_ms == 300 for b in blocos[:-1])


def test_frase_gigante_sem_pontuacao_e_partida_em_palavras():
    frase = " ".join(["palavra"] * 500) + "."
    blocos = dividir(frase, limite=200)
    assert all(len(b.texto) <= 200 for b in blocos)
    assert " ".join(b.texto for b in blocos) == frase


def test_ignora_linhas_sem_conteudo():
    assert dividir("\n  \n...\n") == []
