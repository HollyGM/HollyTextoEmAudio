import pytest

from texto_audio.normalizar import Opcoes, carregar_pronuncias, normalizar


def n(texto, **opcoes):
    return normalizar(texto, Opcoes(**opcoes))


@pytest.mark.parametrize("entrada, esperado", [
    # dispositivos legais
    ("art. 5º, inciso XXXV", "artigo quinto, inciso trinta e cinco"),
    ("arts. 5º e 6º", "artigos quinto e sexto"),
    ("Art. 1.015, § 1º", "Artigo mil e quinze, parágrafo primeiro"),
    ("§§ 1º e 2º", "parágrafos primeiro e segundo"),
    ("incisos I e IV do art. 5º", "incisos primeiro e quarto do artigo quinto"),
    ("1ª Turma", "primeira Turma"),
    ("3ª Vara Cível", "terceira Vara Cível"),
    ("art. 1.015-A", "artigo mil e quinze A"),
    # leis e súmulas
    ("Lei nº 8.078/90", "Lei número oito mil e setenta e oito, de mil novecentos e noventa"),
    ("Lei 13.105/15", "Lei treze mil cento e cinco, de dois mil e quinze"),
    ("Súmula 7/STJ", "Súmula sete do Superior Tribunal de Justiça"),
    ("CF/88", "Constituição Federal de mil novecentos e oitenta e oito"),
    ("CPC/2015", "Código de Processo Civil de dois mil e quinze"),
    # dinheiro, percentual, datas, horas
    ("R$ 10.000,00", "dez mil reais"),
    ("R$ 1,00", "um real"),
    ("R$ 0,50", "cinquenta centavos"),
    ("R$ 1.234,56", "mil duzentos e trinta e quatro reais e cinquenta e seis centavos"),
    ("R$ 1234,56", "mil duzentos e trinta e quatro reais e cinquenta e seis centavos"),
    ("R$ 1000,00", "mil reais"),
    ("R$ 1000000,00", "um milhão de reais"),
    ("R$ 2 milhões", "dois milhões de reais"),
    ("R$ 5 mil", "cinco mil reais"),
    ("R$ 1.000.000,00", "um milhão de reais"),
    ("1,5%", "um vírgula cinco por cento"),
    ("50%", "cinquenta por cento"),
    ("10/03/2024", "dez de março de dois mil e vinte e quatro"),
    ("01/02/2020", "primeiro de fevereiro de dois mil e vinte"),
    ("05/06/20", "cinco de junho de dois mil e vinte"),
    ("às 14h30", "às catorze horas e trinta minutos"),
    ("às 1h", "às uma hora"),
    ("3,14", "três vírgula catorze"),
    ("0,05", "zero vírgula zero cinco"),
    ("2/3 dos votos", "dois terços dos votos"),
    # abreviações
    ("Exmo. Sr. Dr. Juiz", "Excelentíssimo Senhor Doutor Juiz"),
    ("Rel. Min. Fulano", "Relator Ministro Fulano"),
    ("conforme fls. 10/12", "conforme folhas dez a doze"),
    ("Cf. o caso", "Conforme o caso"),
    ("c/c art. 5º", "combinado com artigo quinto"),
    ("e/ou", "e ou"),
    ("art. 10 e ss.", "artigo dez e seguintes"),
    ("p. 45", "página quarenta e cinco"),
])
def test_casos(entrada, esperado):
    saida = n(entrada).rstrip(".")
    assert esperado in saida


def test_min_de_minutos_nao_vira_ministro():
    assert "ministro" not in n("prazo de 30 min. para resposta").lower()


def test_documentos_lidos_digito_a_digito():
    s = n("Processo nº 1234567-89.2023.8.26.0100")
    assert s.startswith("Processo número um dois três quatro cinco seis sete, oito nove,")
    assert "zero um zero zero" in s
    assert "CPF" not in n("CPF 123.456.789-00")          # virou C P F
    assert "C P F" in n("CPF 123.456.789-00")


def test_oab_com_estado_e_numero():
    s = n("OAB/SP 123.456")
    assert "Ordem dos Advogados do Brasil seccional de São Paulo" in s
    assert "cento e vinte e três mil quatrocentos e cinquenta e seis" in s


def test_extenso_entre_parenteses_nao_le_duas_vezes():
    s = n("no valor de R$ 1.500,00 (mil e quinhentos reais) ao mês")
    assert s.count("quinhentos") == 1
    s = n("o prazo de 15 (quinze) dias")
    assert s == "o prazo de quinze dias."
    s = n("multa de 10% (dez por cento)")
    assert s.count("por cento") == 1


def test_parentese_que_nao_e_extenso_e_mantido():
    s = n("prazo de 5 (prorrogável) dias")
    assert "cinco" in s and "prorrogável" in s


@pytest.mark.parametrize("entrada, numero, extenso", [
    ("R$ 100,00 (dez reais)", "cem reais", "dez reais"),
    ("15 (vinte) dias", "quinze", "vinte"),
    ("10% (vinte por cento)", "dez por cento", "vinte por cento"),
])
def test_extenso_divergente_nao_altera_valor_do_documento(entrada, numero, extenso):
    saida = n(entrada)
    assert numero in saida and extenso in saida


def test_extenso_equivalente_aceita_genero_e_conectivos():
    assert n("2 (duas) horas") == "duas horas."
    assert n("1500 (mil e quinhentos) reais") == "mil e quinhentos reais."


def test_siglas_extenso_e_letras():
    assert "Supremo Tribunal Federal" in n("O STF decidiu")
    assert "S T F" in n("O STF decidiu", siglas="letras")
    # siglas de peças são sempre expandidas
    assert "Recurso Especial" in n("o REsp 123", siglas="letras")


def test_sigla_ambigua_so_com_numero():
    assert "Mandado de Segurança" in n("no MS 12345")
    assert "Mato Grosso do Sul" not in n("no MS 12345")
    assert "Medida Provisória" in n("a MP 1.045")
    assert "Ministério Público" in n("o MP requereu")


def test_tribunais_regionais_e_estaduais():
    assert "Tribunal de Justiça de São Paulo" in n("TJSP")
    assert "Tribunal de Justiça de Minas Gerais" in n("TJ/MG")
    assert "Tribunal Regional Federal da terceira Região" in n("TRF3")
    assert "Tribunal Regional Federal da terceira Região" in n("TRF da 3ª Região").replace(
        "Tribunal Regional Federal da terceira", "Tribunal Regional Federal da terceira")
    assert "Tribunal Regional do Trabalho da segunda Região" in n("TRT-2")


def test_estado_depois_de_numero_de_recurso():
    assert ", de São Paulo" in n("REsp 1.234.567/SP")
    assert ", do Rio Grande do Norte" in n("REsp 1.234.567/RN")


@pytest.mark.parametrize("entrada, esperado", [
    ("TJRN", "Tribunal de Justiça do Rio Grande do Norte"),
    ("TJBA", "Tribunal de Justiça da Bahia"),
    ("TJPB", "Tribunal de Justiça da Paraíba"),
    ("TJAM", "Tribunal de Justiça do Amazonas"),
    ("TJPE", "Tribunal de Justiça de Pernambuco"),
    ("OAB/RN 10.432", "Ordem dos Advogados do Brasil seccional do Rio Grande do Norte"),
])
def test_preposicao_do_estado(entrada, esperado):
    assert esperado in n(entrada)


def test_todo_estado_tem_preposicao():
    from texto_audio import dados
    assert set(dados.PREPOSICAO_ESTADO) == set(dados.ESTADOS)
    assert set(dados.PREPOSICAO_ESTADO.values()) <= {"de", "do", "da"}


@pytest.mark.parametrize("entrada, esperado", [
    ("art. 157, § 2º, II, do CP",
     "artigo cento e cinquenta e sete, parágrafo segundo, inciso segundo, do Código Penal"),
    ("art. 5º, LIV e LV, da CF",
     "artigo quinto, incisos cinquenta e quatro e cinquenta e cinco, da Constituição Federal"),
    ("art. 121, parágrafo único, I, do CP",
     "artigo cento e vinte e um, parágrafo único, inciso primeiro, do Código Penal"),
    ("art. 5º, LXVIII, da CF", "artigo quinto, inciso sessenta e oito, da Constituição Federal"),
    ("art. 157, I a III", "artigo cento e cinquenta e sete, incisos primeiro a terceiro"),
    ("ART. 157, § 2º, II, DO CP", "inciso segundo"),
])
def test_inciso_citado_sem_a_palavra_inciso(entrada, esperado):
    assert esperado in n(entrada)


def test_romano_fora_de_citacao_nao_vira_inciso():
    assert "inciso" not in n("art. 186, CC e art. 927 do CC")
    assert "Código Civil" in n("art. 186, CC")
    assert "Dom Pedro II" in n("Dom Pedro II")


def test_cf_em_caixa_alta_no_fim_da_frase_e_a_constituicao():
    assert n("Viola a CF.").endswith("Constituição Federal.")
    assert n("cf. o voto").startswith("conforme")
    assert n("Cf. o voto").startswith("Conforme")


def test_latim():
    s = n("Data venia, o caput do artigo exige fumus boni iuris.")
    assert s.startswith("Dáta vênia")
    assert "cápute" in s and "fúmus bóni iúris" in s
    assert "rábeas córpus" in n("impetrou habeas corpus")
    assert "rábeas córpus" in n("o HC 123")


def test_titulo_em_caixa_alta_vira_minuscula():
    s = n("EXCELENTÍSSIMO SENHOR DOUTOR JUIZ DE DIREITO DA 3ª VARA CÍVEL")
    assert s == "excelentíssimo senhor doutor juiz de direito da terceira vara cível."
    # sigla dentro do título sobrevive
    assert "Supremo Tribunal Federal" in n("RECURSO AO STF")
    assert "são paulo SP" in n("COMARCA DE SÃO PAULO/SP")


def test_numeracao_de_topicos():
    assert n("I – DOS FATOS\nTexto.") == "dos fatos.\nTexto."
    assert n("1. O autor requereu.") == "O autor requereu."
    assert n("a) o pagamento") == "o pagamento."
    assert n("I – DOS FATOS", omitir_numeracao=False).startswith("um,")


def test_referencias_opcionais():
    texto = "O contrato foi assinado (fls. 12) e pago (Id. 98765, p. 4)."
    assert "folhas" in n(texto)
    assert n(texto, omitir_referencias=True) == "O contrato foi assinado e pago."
    # parêntese comum não é referência
    assert "importante" in n("o pedido (documento importante) foi feito", omitir_referencias=True)


def test_quebra_de_linha_de_pdf():
    s = n("O autor requereu a tutela de ur-\ngência, nos termos da lei e\ndo regimento interno.")
    assert s == "O autor requereu a tutela de urgência, nos termos da lei e do regimento interno."


def test_paragrafos_ficam_em_linhas_separadas_e_ganham_ponto_final():
    assert n("Primeiro parágrafo\n\nSegundo parágrafo.") == "Primeiro parágrafo.\nSegundo parágrafo."


def test_limpeza_de_lixo_de_formatacao():
    s = n("**Importante**: veja https://exemplo.com/x e a nota[1].")
    assert "http" not in s and "*" not in s and "[" not in s


def test_pronuncias_personalizadas():
    mapa = carregar_pronuncias("# comentário\nBNDES = bê ene dê é ésse\nsem igual\n")
    assert mapa == {"BNDES": "bê ene dê é ésse"}
    assert n("financiado pelo BNDES.", pronuncias=mapa) == "financiado pelo bê ene dê é ésse."


def test_nao_quebra_com_entradas_estranhas():
    for t in ["", "   ", "!!!", "12", "R$", "§", "º", "()", "a/b/c", "99/99/9999", "1/0"]:
        assert isinstance(normalizar(t), str)


def test_texto_grande_e_rapido():
    import time
    base = ("Nos termos do art. 5º, inciso XXXV, da CF/88, e da Lei nº 8.078/90, "
            "o valor de R$ 10.000,00 (dez mil reais) é devido, conforme o STJ. ")
    texto = (base * 12 + "\n") * 500        # ~100 mil palavras
    inicio = time.time()
    normalizar(texto)
    assert time.time() - inicio < 15
