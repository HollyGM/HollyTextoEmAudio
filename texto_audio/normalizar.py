"""Normalização de texto jurídico pt-BR para leitura por voz sintética.

A voz neural lê bem prosa corrente, mas tropeça em tudo o que é típico de peça
processual: "art. 5º, § 1º", "Lei nº 8.078/90", "R$ 10.000,00 (dez mil reais)",
números de processo, siglas de tribunais, expressões latinas. Este módulo
reescreve o texto do jeito que um advogado o diria em voz alta.

A função pública é `normalizar(texto, Opcoes)`. Cada etapa é uma função pequena
e pura, aplicada em ordem fixa (a ordem importa: veja o corpo de `normalizar`).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from num2words import num2words

from . import dados

UNIDADES = ["zero", "um", "dois", "três", "quatro", "cinco", "seis", "sete",
            "oito", "nove"]

_ROMANO = (r"(?=[IVXLCDM])M{0,3}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})"
           r"(?:IX|IV|V?I{0,3})")
_ROMANO_ATE_39 = r"(?=[IVX])X{0,3}(?:IX|IV|V?I{0,3})"
_UF = "|".join(dados.ESTADOS)


@dataclass
class Opcoes:
    siglas: str = "extenso"            # "extenso" ou "letras" (S T F)
    omitir_referencias: bool = False   # tira "(fls. 12)", "(Id. 123)", "(p. 4)"
    omitir_numeracao: bool = True      # tira "I –", "1.", "a)" no início da linha
    pronuncias: dict[str, str] = field(default_factory=dict)


# --------------------------------------------------------------------------
# números
# --------------------------------------------------------------------------

def cardinal(n: int) -> str:
    # num2words põe vírgula depois do "mil" ("mil, duzentos"), o que a voz lê
    # como pausa. Tiramos.
    return num2words(n, lang="pt_BR").replace(",", "")


def ordinal(n: int, feminino: bool = False) -> str:
    txt = num2words(n, lang="pt_BR", to="ordinal").replace(",", "")
    if feminino:
        txt = " ".join(p[:-1] + "a" if p.endswith("o") else p
                       for p in txt.split())
    return txt


def _feminino(txt: str) -> str:
    return re.sub(r"\bdois\b", "duas", re.sub(r"\bum\b", "uma", txt))


def _digitos(s: str) -> str:
    return " ".join(UNIDADES[int(c)] for c in s if c.isdigit())


def _inteiro(s: str) -> str:
    """Lê uma sequência de dígitos (sem separadores)."""
    if len(s) > 9 or (len(s) > 1 and s.startswith("0")):
        return _digitos(s)       # protocolo, código: dígito a dígito
    return cardinal(int(s))


def _decimal(parte_int: str, parte_frac: str) -> str:
    inteiro = _inteiro(parte_int.replace(".", ""))
    zeros = len(parte_frac) - len(parte_frac.lstrip("0"))
    resto = parte_frac.lstrip("0")
    if not resto:
        frac = " ".join(["zero"] * len(parte_frac))
    elif len(resto) <= 3:
        frac = " ".join(["zero"] * zeros + [cardinal(int(resto))])
    else:
        frac = _digitos(parte_frac)
    return f"{inteiro} vírgula {frac}"


def _ano(s: str) -> str:
    if len(s) == 4:
        return s
    return str(2000 + int(s) if int(s) <= 30 else 1900 + int(s))


# --------------------------------------------------------------------------
# etapas
# --------------------------------------------------------------------------

def _limpar(t: str) -> str:
    t = unicodedata.normalize("NFC", t)
    for ch in ("\u00ad", "\u200b", "\u200c", "\u200d", "\ufeff"):
        t = t.replace(ch, "")
    t = t.replace("\u00a0", " ").replace("\u2028", "\n").replace("\u2029", "\n")
    t = re.sub(r"\r\n?", "\n", t)
    t = re.sub(r"https?://\S+|www\.\S+", "", t)
    t = re.sub(r"\[\d{1,3}\]", "", t)                 # notas [1]
    t = re.sub(r"_{2,}", " ", t)                       # linhas de assinatura
    t = re.sub(r"[*`]+", "", t)                        # markdown
    t = re.sub(r"^\s{0,3}#{1,6}\s*", "", t, flags=re.M)
    t = re.sub(r"^\s*[•▪◦●■\-–—]\s+", "", t, flags=re.M)   # marcadores
    # PDF: junta linha quebrada no meio da frase e palavra hifenizada
    t = re.sub(r"(\w)-\n(?=[a-zà-ú])", r"\1", t)
    t = re.sub(r"(?<![.!?:;\n])\n(?=[a-zà-ú])", " ", t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n", t)
    return t.strip()


_PRONUNCIAS_RE_CACHE: dict[tuple, re.Pattern] = {}


def _aplicar_pronuncias(t: str, mapa: dict[str, str]) -> str:
    if not mapa:
        return t
    chave = tuple(sorted(mapa))
    rx = _PRONUNCIAS_RE_CACHE.get(chave)
    if rx is None:
        alternativas = sorted(mapa, key=len, reverse=True)
        rx = re.compile(
            r"(?<!\w)(?:" + "|".join(re.escape(a) for a in alternativas)
            + r")(?!\w)", re.IGNORECASE)
        _PRONUNCIAS_RE_CACHE[chave] = rx
    baixo = {k.lower(): v for k, v in mapa.items()}
    return rx.sub(lambda m: baixo[m.group(0).lower()], t)


_RE_NUMERACAO_ROMANA = re.compile(
    rf"^[ \t]*(?:{_ROMANO_ATE_39})[ \t]*[.)\-–—][ \t]*(?=\S)", re.M)
_RE_NUMERACAO_ROMANA_LEITURA = re.compile(
    rf"^[ \t]*({_ROMANO_ATE_39})(?=[ \t]*[.)\-–—])", re.M)
_RE_NUMERACAO_ARABICA = re.compile(
    r"^[ \t]*\d{1,3}(?:\.\d{1,3})*[ \t]*[.)\-–—][ \t]+(?=\S)", re.M)
_RE_NUMERACAO_LETRA = re.compile(r"^[ \t]*\(?[a-z]\)[ \t]+(?=\S)", re.M)


def _numeracao(t: str, op: Opcoes) -> str:
    if op.omitir_numeracao:
        t = _RE_NUMERACAO_ROMANA.sub("", t)
        t = _RE_NUMERACAO_ARABICA.sub("", t)
        t = _RE_NUMERACAO_LETRA.sub("", t)
    else:
        t = _RE_NUMERACAO_ROMANA_LEITURA.sub(
            lambda m: cardinal(_romano_para_int(m.group(1))), t)
    return t


_RE_REFERENCIA = re.compile(
    r"\(\s*(?:fls?\.?|folhas?|ids?\.?|eventos?|docs?\.?|documentos?|pp?\."
    r"|págs?\.?|num\.?|seq\.?)(?:[\s,]*pp?\.)?[\s,.nº°]*\d[^()]*\)",
    re.IGNORECASE)


def _omitir_referencias(t: str) -> str:
    return _RE_REFERENCIA.sub("", t)


def _numero_abrev(t: str) -> str:
    """nº, n.º, n° e n. (antes de dígito) -> número."""
    def troca(m):
        return ("Número" if m.group(1) == "N" else "número") + m.group(2)
    t = re.sub(r"\b([Nn])\.?\s*[º°](s?)", troca, t)
    return re.sub(r"\b([Nn])\.\s*(?=\d)()", troca, t)


_VOCAB_EXTENSO = {p for i in range(1000) for p in cardinal(i).split()}
_VOCAB_EXTENSO |= {"mil", "milhão", "milhões", "bilhão", "bilhões", "e", "de",
                   "uma", "duas", "meio", "meia", "cem", "real", "reais",
                   "centavo", "centavos", "por", "cento", "vírgula"}
_RE_EXTENSO = re.compile(
    r"(?P<num>R\$\s*\d[\d.]*(?:,\d+)?"
    r"(?:\s*(?:mil|milh[ãa]o|milh[õo]es|bilh[ãa]o|bilh[õo]es))?"
    r"|\d[\d.]*(?:,\d+)?\s*%|\d[\d.]*(?:,\d+)?)\s*\((?P<ext>[^()]{1,200})\)",
    re.IGNORECASE)


def _extenso_entre_parenteses(t: str) -> str:
    """'R$ 1.500,00 (mil e quinhentos reais)' -> só o extenso (não lê duas vezes)."""
    def troca(m):
        ext = m.group("ext").strip()
        palavras = re.findall(r"[a-zà-ú]+", ext.lower())
        if not palavras or not all(p in _VOCAB_EXTENSO for p in palavras):
            return m.group(0)
        if not (set(palavras) - {"e", "de", "por"}):
            return m.group(0)
        num = m.group("num")
        if num.upper().startswith("R$") and not (
                {"real", "reais", "centavo", "centavos"} & set(palavras)):
            return m.group(0)
        if num.endswith("%") and "cento" not in palavras:
            return m.group(0)
        # Eliminar a repetição só é seguro quando as duas grafias dizem o
        # mesmo valor. Uma divergência no documento deve continuar audível.
        esperado = _numeros(_moeda_e_percentual(num))

        def comparar(txt):
            tokens = re.findall(r"[a-zà-ú]+", txt.lower())
            genero = {"uma": "um", "duas": "dois", "meia": "meio"}
            return [genero.get(p, p) for p in tokens if p not in {"e", "de"}]

        if re.search(r"\d", ext) or comparar(ext) != comparar(esperado):
            return m.group(0)
        return ext
    return _RE_EXTENSO.sub(troca, t)


def _ler_documento(m: re.Match) -> str:
    grupos = re.split(r"\D+", m.group(0))
    return ", ".join(_digitos(g) for g in grupos if g)


_RE_CNJ = re.compile(r"\b\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}\b")
_RE_CPF = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")
_RE_CNPJ = re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b")
_RE_OAB = re.compile(
    rf"(?<![\w/])OAB\s*[/\-]\s*(?P<uf>{_UF})\b"
    r"(?:\s*(?:n[º°.]*\s*|número\s+)?(?P<num>\d{1,3}(?:\.\d{3})+|\d{3,7})\b)?")


def _documentos(t: str) -> str:
    for rx in (_RE_CNJ, _RE_CNPJ, _RE_CPF):
        t = rx.sub(_ler_documento, t)

    def oab(m):
        s = f"OAB seccional {dados.de_estado(m.group('uf'))}"
        if m.group("num"):
            s += f", número {m.group('num')}"
        return s
    return _RE_OAB.sub(oab, t)


_RE_DATA = re.compile(r"\b(\d{1,2})([/.\-])(\d{1,2})\2(\d{4}|\d{2})\b")
_RE_HORA_H = re.compile(r"\b([01]?\d|2[0-3])\s*h\s*([0-5]\d)?(?:\s*min)?\b")
_RE_HORA_DOIS_PONTOS = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")


def _datas_e_horas(t: str) -> str:
    def data(m):
        d, mes, a = int(m.group(1)), int(m.group(3)), m.group(4)
        if not (1 <= d <= 31 and 1 <= mes <= 12):
            return m.group(0)
        dia = "primeiro" if d == 1 else str(d)
        return f"{dia} de {dados.MESES[mes - 1]} de {_ano(a)}"

    def hora(m):
        h, minutos = int(m.group(1)), m.group(2)
        s = _feminino(cardinal(h)) + (" hora" if h == 1 else " horas")
        if minutos and int(minutos):
            mi = int(minutos)
            s += f" e {cardinal(mi)} " + ("minuto" if mi == 1 else "minutos")
        return s

    t = _RE_DATA.sub(data, t)
    t = _RE_HORA_H.sub(hora, t)
    return _RE_HORA_DOIS_PONTOS.sub(hora, t)


_RE_MOEDA = re.compile(
    r"R\$\s*(?P<int>\d{1,3}(?:\.\d{3})+|\d+)(?:,(?P<cent>\d{1,2}))?"
    r"(?:\s*(?P<esc>mil|milh[ãa]o|milh[õo]es|bilh[ãa]o|bilh[õo]es)\b)?",
    re.IGNORECASE)
_RE_PERCENTUAL = re.compile(r"(\d{1,3}(?:\.\d{3})*|\d+)(?:,(\d+))?\s*%")


def _moeda_e_percentual(t: str) -> str:
    def moeda(m):
        inteiro = m.group("int").replace(".", "")
        cent = m.group("cent")
        esc = m.group("esc")
        if esc:
            esc_l = esc.lower().replace("ao", "ão").replace("oes", "ões")
            valor = (_decimal(inteiro, cent) if cent else _inteiro(inteiro))
            de = "" if esc_l == "mil" else " de"
            return f"{valor} {esc_l}{de} reais"
        reais = int(inteiro)
        centavos = int(cent.ljust(2, "0")) if cent else 0
        partes = []
        if reais or not centavos:
            de = " de" if reais >= 1_000_000 and reais % 1_000_000 == 0 else ""
            partes.append(f"{_inteiro(inteiro)}{de} "
                          + ("real" if reais == 1 else "reais"))
        if centavos:
            partes.append(f"{cardinal(centavos)} "
                          + ("centavo" if centavos == 1 else "centavos"))
        return " e ".join(partes)

    def percentual(m):
        if m.group(2):
            return _decimal(m.group(1), m.group(2)) + " por cento"
        return _inteiro(m.group(1).replace(".", "")) + " por cento"

    t = _RE_MOEDA.sub(moeda, t)
    return _RE_PERCENTUAL.sub(percentual, t)


_RE_SUMULA = re.compile(
    r"\b(S[úu]mulas?(?:\s+Vinculantes?)?)\s*(?:n[º°.]*\s*|número\s+)?(\d+)"
    r"\s*/\s*(STF|STJ|TST|TSE|STM)\b")
_RE_NORMA_ANO = re.compile(
    r"(?<![\d/.,])(?P<n>\d{1,3}(?:\.\d{3})*|\d+)\s*/\s*"
    r"(?P<a>(?:19|20)\d{2}|\d{2})(?![\d/])")
_RE_FRACAO = re.compile(r"(?<![\d/.,])([1-9])/([2-9]|10)(?![\d/])")
_FRACOES = {2: "meio", 3: "terço", 4: "quarto", 5: "quinto", 6: "sexto",
            7: "sétimo", 8: "oitavo", 9: "nono", 10: "décimo"}


def _normas_e_fracoes(t: str) -> str:
    # "REsp 1.234.567/SP": o /SP é o estado de origem
    t = re.sub(rf"(?<=\d)[ \t]*/[ \t]*({_UF})(?![\w/])",
               lambda m: f", {dados.de_estado(m.group(1))}", t)
    t = re.sub(r"(?i:\bfls?\.?)\s*(\d+)\s*/\s*(\d+)",
               lambda m: f"folhas {m.group(1)} a {m.group(2)}", t)
    t = _RE_SUMULA.sub(lambda m: f"{m.group(1)} {m.group(2)} do {m.group(3)}", t)

    def norma(m):
        ano = m.group("a")
        if len(ano) == 2 and len(m.group("n").replace(".", "")) < 3:
            return m.group(0)       # "50/50": não é Lei 50/50
        return f"{m.group('n')}, de {_ano(ano)}"
    t = _RE_NORMA_ANO.sub(norma, t)

    def fracao(m):
        num, den = int(m.group(1)), int(m.group(2))
        if num == 1 and den == 2:
            return "metade"
        nome = _FRACOES[den] + ("s" if num > 1 else "")
        return f"{cardinal(num)} {nome}"
    return _RE_FRACAO.sub(fracao, t)


_RE_ORDINAL = re.compile(r"(\d+)\s*([ºª°])")


def _ordinais_e_paragrafos(t: str) -> str:
    t = re.sub(r"§§\s*", "parágrafos ", t)
    t = re.sub(r"§\s*", "parágrafo ", t)
    return _RE_ORDINAL.sub(
        lambda m: ordinal(int(m.group(1)), feminino=m.group(2) == "ª"), t)


_RE_ROMANO_CTX = re.compile(
    r"\b(?P<kw>(?i:incisos?|cap[ií]tulos?|t[ií]tulos?|se[çc][ãa]o|se[çc][õo]es"
    r"|livros?|tomos?|s[ée]culos?|anexos?|classes?|fase))\s+"
    rf"(?P<seq>\b(?:{_ROMANO})\b(?:\s*(?:,|e|a|ao)\s*\b(?:{_ROMANO})\b)*)")
_RE_TOKEN_ROMANO = re.compile(rf"\b(?:{_ROMANO})\b")
_VALORES_ROMANOS = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500,
                    "M": 1000}


def _romano_para_int(r: str) -> int:
    total = 0
    for i, c in enumerate(r):
        v = _VALORES_ROMANOS[c]
        total += -v if i + 1 < len(r) and _VALORES_ROMANOS[r[i + 1]] > v else v
    return total


# Inciso citado sem a palavra "inciso": "art. 157, § 2º, II, do CP" e
# "art. 5º, LIV e LV, da CF". Roda depois dos ordinais e parágrafos, então o
# trecho já está como "art. 157, parágrafo segundo, II".
_ORDINAL_POR_EXTENSO = (r"(?:primeiro|segundo|terceiro|quarto|quinto|sexto"
                        r"|s[ée]timo|oitavo|nono)")
_RE_INCISO_CITADO = re.compile(
    r"(?P<pre>\b(?i:arts?\.|artigos?)\s*(?:\d[\d.]*(?:-[A-Z])?|"
    + _ORDINAL_POR_EXTENSO + r")"
    r"(?:\s*,\s*(?:caput|par[áa]grafos?\s+(?:[úu]nico|"
    + _ORDINAL_POR_EXTENSO + r"|\d+)))*\s*,\s*)"
    rf"(?P<seq>\b(?:{_ROMANO})\b(?:\s*(?:,|e|a)\s*\b(?:{_ROMANO})\b)*)"
    r"(?=\s*(?:[,;.:)]|$)|\s+(?:e|do|da|dos|das|c/c|combinad[oa])\b)")
# Inciso passa de LXXVIII só em lei muito longa; o teto evita ler "CC" (200)
# ou "DL" (550) como inciso.
_MAIOR_INCISO = 89


def _incisos_citados(t: str) -> str:
    def troca(m):
        romanos = _RE_TOKEN_ROMANO.findall(m.group("seq"))
        valores = [_romano_para_int(r) for r in romanos]
        if not valores or max(valores) > _MAIOR_INCISO:
            return m.group(0)

        def um(r):
            n = _romano_para_int(r.group(0))
            return ordinal(n) if n <= 9 else cardinal(n)
        rotulo = "incisos" if len(romanos) > 1 else "inciso"
        return (m.group("pre") + rotulo + " "
                + _RE_TOKEN_ROMANO.sub(um, m.group("seq")))
    return _RE_INCISO_CITADO.sub(troca, t)


def _romanos_contextuais(t: str) -> str:
    def troca(m):
        inciso = m.group("kw").lower().startswith("inciso")

        def um(r):
            n = _romano_para_int(r.group(0))
            return ordinal(n) if inciso and n <= 9 else cardinal(n)
        return m.group("kw") + " " + _RE_TOKEN_ROMANO.sub(um, m.group("seq"))
    return _RE_ROMANO_CTX.sub(troca, _incisos_citados(t))


def _maiuscula_inicial(origem: str, texto: str) -> str:
    if origem.isupper() and len(origem) > 1:
        return texto.upper()
    if origem[:1].isupper():
        return texto[:1].upper() + texto[1:]
    return texto


# Títulos só valem com inicial maiúscula ("Min." mas não "30 min.").
_ABREV_EXIGEM_MAIUSCULA = {
    "exmo", "exma", "exmos", "exmas", "ilmo", "ilma", "sr", "sra", "srs",
    "sras", "dr", "dra", "drs", "profa", "prof", "min", "des", "desa", "dep",
    "rel", "adv", "av",
}
# Em caixa alta são siglas, não abreviações: "da CF." é a Constituição Federal
# no fim da frase, não "conforme" ("cf." e "Cf." continuam sendo "conforme").
_ABREV_QUE_EM_CAIXA_ALTA_SAO_SIGLA = {"cf"}
_RE_ABREV = re.compile(
    r"(?<![\w.])(" + "|".join(sorted(map(re.escape, dados.ABREVIACOES),
                                     key=len, reverse=True)) + r")\.",
    re.IGNORECASE)


def _abreviacoes(t: str) -> str:
    # expressões com pontos internos
    for padrao, leitura in (
        (r"\bet\s+al\.", "e outros"),
        (r"\bc\s*/\s*c\b\.?", "combinado com"),
        (r"\bp\.\s*ex\.?", "por exemplo"),
        (r"\bv\.\s*g\.?", "por exemplo"),
        (r"\bi\.\s*e\.?", "isto é"),
        (r"\be\.\s*g\.?", "por exemplo"),
        (r"\bv\.\s*u\.?", "votação unânime"),
        (r"\be/ou\b", "e ou"),
    ):
        t = re.sub(padrao, leitura, t, flags=re.IGNORECASE)
    # dependentes de contexto
    t = re.sub(r"\bpp\.\s*(?=\d)", "páginas ", t, flags=re.IGNORECASE)
    t = re.sub(r"\bp\.\s*(?=\d)", "página ", t, flags=re.IGNORECASE)
    t = re.sub(r"\bj\.\s*(?=\d)", "julgado em ", t)
    t = re.sub(r"\bal\.\s*(?=[\"“']?[a-z]\b)", "alínea ", t)

    def etc(m):
        depois = m.string[m.end():m.end() + 4]
        fim = re.match(r"\s*$|\s+[A-ZÀ-Ú]", depois) is not None
        return _maiuscula_inicial(m.group(0), "et cétera") + ("." if fim else "")
    t = re.sub(r"\betc\.", etc, t, flags=re.IGNORECASE)

    def troca(m):
        chave = m.group(1)
        baixa = chave.lower()
        if baixa in _ABREV_EXIGEM_MAIUSCULA and not chave[0].isupper():
            return m.group(0)
        if baixa in _ABREV_QUE_EM_CAIXA_ALTA_SAO_SIGLA and chave.isupper():
            return m.group(0)
        return _maiuscula_inicial(chave, dados.ABREVIACOES[baixa])
    return _RE_ABREV.sub(troca, t)


_ALT_SIGLAS = "|".join(sorted(
    list(dados.SIGLAS) + list(dados.PECAS_E_RECURSOS)
    + list(dados.SIGLAS_SEMPRE_LETRAS), key=len, reverse=True))
_RE_SIGLA = re.compile(rf"(?<![\w/])({_ALT_SIGLAS})(?![\w])")
_RE_SIGLA_SO_NUM = re.compile(
    r"(?<![\w/])(" + "|".join(sorted(dados.SIGLAS_SO_COM_NUMERO,
                                    key=len, reverse=True))
    + r")(?=\s+(?:número\s+)?\d)")
_RE_TJ_UF = re.compile(rf"(?<![\w/])TJ\s?[-/]?\s?({_UF})(?![\w])")
_RE_REGIONAL = re.compile(
    r"(?<![\w/])TR(F|T)\s?-?\s?(\d{1,2})(?!\d)(?:\s*[ªaº°]\s*Regi[ãa]o)?")
_LEIS_COM_ANO = ("CRFB", "LINDB", "LGPD", "CPC", "CPP", "CDC", "CLT", "CTN",
                 "CTB", "ECA", "LEP", "CF", "CC", "CP")
_RE_CF_ANO = re.compile(
    r"(?<![\w/])(" + "|".join(_LEIS_COM_ANO)
    + r")\s*/\s*((?:19|20)\d{2}|\d{2})(?!\d)")


def _tribunais(t: str, op: Opcoes) -> str:
    """TJSP, TRF3, TRT-2... (roda antes dos ordinais, que consumiriam o 3ª)."""
    t = _RE_TJ_UF.sub(
        lambda m: ("T J " + " ".join(m.group(1))) if op.siglas == "letras"
        else f"Tribunal de Justiça {dados.de_estado(m.group(1))}", t)

    def regional(m):
        n = ordinal(int(m.group(2)), feminino=True)
        if m.group(1) == "F":
            return f"Tribunal Regional Federal da {n} Região"
        return f"Tribunal Regional do Trabalho da {n} Região"
    return _RE_REGIONAL.sub(regional, t)


def _siglas(t: str, op: Opcoes) -> str:
    letras = op.siglas == "letras"

    def soletrar(s: str) -> str:
        return " ".join(s)

    def expandir(s: str) -> str:
        if s in dados.SIGLAS_SEMPRE_LETRAS:
            return soletrar(s)
        if s in dados.PECAS_E_RECURSOS:
            return dados.PECAS_E_RECURSOS[s]
        if letras and s.isupper():
            return soletrar(s)
        return dados.SIGLAS[s]

    t = _RE_CF_ANO.sub(
        lambda m: f"{expandir(m.group(1))} de {_ano(m.group(2))}", t)
    t = _RE_SIGLA_SO_NUM.sub(lambda m: dados.SIGLAS_SO_COM_NUMERO[m.group(1)], t)
    return _RE_SIGLA.sub(lambda m: expandir(m.group(1)), t)


def _numeros(t: str) -> str:
    t = re.sub(r"(?<=\d)-(?=[A-Z]\b)", " ", t)              # 1.015-A
    t = re.sub(
        r"(?<![\d.,])(\d{1,3}(?:\.\d{3})*|\d+),(\d+)(?!\d)",
        lambda m: _decimal(m.group(1), m.group(2)), t)
    t = re.sub(r"(?<![\d.,])\d{1,3}(?:\.\d{3})+(?!\d)",
               lambda m: _inteiro(m.group(0).replace(".", "")), t)
    t = re.sub(r"(?<![\d.])\d+(?!\d)", lambda m: _inteiro(m.group(0)), t)
    return t


_RE_PALAVRA_CAIXA_ALTA = re.compile(r"\b[A-ZÀ-Ú]{2,}\b")
_PROTEGIDAS = (set(dados.SIGLAS) | set(dados.PECAS_E_RECURSOS)
               | set(dados.SIGLAS_SO_COM_NUMERO) | dados.SIGLAS_SEMPRE_LETRAS)
_RE_PROTEGIDA = re.compile(
    rf"TJ(?:{_UF})|TR[FT]|{_ROMANO_ATE_39}|CRFB|OAB")


def _linhas_de_titulo(t: str) -> set[int]:
    """Índices das linhas todas em CAIXA ALTA.

    Precisa rodar cedo: depois que "3ª" vira "terceira" a linha deixa de ser
    toda maiúscula. Nenhuma etapa intermediária cria ou remove quebras de
    linha, então os índices valem até `_pontuacao`.
    """
    indices = set()
    for i, linha in enumerate(t.split("\n")):
        letras = [c for c in linha if c.isalpha() and c not in "ªº"]
        if len(letras) > 3 and all(c.isupper() for c in letras):
            indices.add(i)
    return indices


def _caixa_alta(t: str, titulos: set[int]) -> str:
    """Título em CAIXA ALTA vira minúscula (a voz soletraria "DO", "DA").

    Siglas conhecidas ficam intactas; fora de títulos só palavras com 6+
    letras são rebaixadas (as curtas costumam ser siglas).
    """
    def baixa(m, minimo):
        tok = m.group(0)
        if (tok in _PROTEGIDAS or _RE_PROTEGIDA.fullmatch(tok)
                or len(tok) < minimo
                or (tok in dados.ESTADOS and m.string[m.start() - 1:m.start()]
                    in ("/", "-"))):
            return tok
        return tok.lower()

    linhas = []
    for i, linha in enumerate(t.split("\n")):
        minimo = 2 if i in titulos else 6
        linhas.append(_RE_PALAVRA_CAIXA_ALTA.sub(
            lambda m: baixa(m, minimo), linha))
    return "\n".join(linhas)


_RE_PRONUNCIAS_PADRAO = re.compile(
    r"(?<!\w)(?:" + "|".join(re.escape(k) for k in sorted(
        dados.PRONUNCIAS_PADRAO, key=len, reverse=True)) + r")(?!\w)",
    re.IGNORECASE)


def _ler_latim(m: re.Match) -> str:
    """Respelling da expressão; a inicial maiúscula só se abre a frase."""
    leitura = dados.PRONUNCIAS_PADRAO[m.group(0).lower()]
    antes = m.string[:m.start()].rstrip(" ")
    if not antes or antes[-1] in ".!?:\n":
        return _maiuscula_inicial(m.group(0), leitura)
    return leitura


def _pontuacao(t: str) -> str:
    t = re.sub(r"(?<=\d)[ \t]*/[ \t]*(?=\d)", " barra ", t)
    t = t.replace("/", " ")
    t = re.sub(r"(?<=\d)-(?=\d)", ", ", t)
    t = re.sub(r"[ \t]+[–—-][ \t]+", ", ", t)
    t = t.replace("–", ", ").replace("—", ", ")
    t = re.sub(r"[\"“”«»]", "", t)
    t = t.replace("…", ".").replace("...", ".")
    t = re.sub(r"[ \t]*\([ \t]*", ", ", t)
    t = re.sub(r"[ \t]*\)[ \t]*", ", ", t)
    t = re.sub(r"\[|\]", "", t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"[ \t]+([,.;:!?])", r"\1", t)
    t = re.sub(r"([,;:])[ \t]*([,.;:!?])", r"\2", t)
    t = re.sub(r",[ \t]*,+", ",", t)
    t = re.sub(r"\.{2,}", ".", t)
    linhas = []
    for linha in t.split("\n"):
        linha = re.sub(r"^[\s,;:]+", "", linha).strip(" ,")
        if not linha:
            continue
        if not re.search(r"[.!?:;]$", linha):
            linha += "."
        linhas.append(linha)
    return "\n".join(linhas)


# --------------------------------------------------------------------------
# API pública
# --------------------------------------------------------------------------

def normalizar(texto: str, op: Opcoes | None = None) -> str:
    """Devolve o texto reescrito para ser lido em voz alta.

    Parágrafos ficam separados por uma quebra de linha.
    """
    op = op or Opcoes()
    t = _limpar(texto)
    t = _aplicar_pronuncias(t, op.pronuncias)
    titulos = _linhas_de_titulo(t)
    t = _numeracao(t, op)
    if op.omitir_referencias:
        t = _omitir_referencias(t)
    t = _numero_abrev(t)
    t = _extenso_entre_parenteses(t)
    t = _documentos(t)
    t = _datas_e_horas(t)
    t = _moeda_e_percentual(t)
    t = _normas_e_fracoes(t)
    t = _tribunais(t, op)
    t = _ordinais_e_paragrafos(t)
    t = _romanos_contextuais(t)
    t = _abreviacoes(t)
    t = _caixa_alta(t, titulos)
    t = _siglas(t, op)
    t = _numeros(t)
    t = _RE_PRONUNCIAS_PADRAO.sub(_ler_latim, t)
    return _pontuacao(t)


def contar_palavras(texto: str) -> int:
    return len(re.findall(r"[\wÀ-ÿ]+", texto))


def carregar_pronuncias(texto: str) -> dict[str, str]:
    """Lê linhas `termo = leitura` (ignora vazias e comentários com #)."""
    mapa: dict[str, str] = {}
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        termo, leitura = (p.strip() for p in linha.split("=", 1))
        if termo and leitura:
            mapa[termo] = leitura
    return mapa
