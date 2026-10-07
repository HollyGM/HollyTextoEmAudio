"""Extrai texto de arquivos enviados (.txt, .md, .docx, .pdf)."""
from __future__ import annotations

import io
from pathlib import Path


class ArquivoNaoSuportado(Exception):
    pass


def _texto_puro(dados: bytes) -> str:
    if dados.startswith((b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff")):
        return dados.decode("utf-32")
    if dados.startswith((b"\xff\xfe", b"\xfe\xff")):
        return dados.decode("utf-16")
    for codificacao in ("utf-8-sig", "cp1252"):
        try:
            return dados.decode(codificacao)
        except UnicodeDecodeError:
            continue
    return dados.decode("latin-1")


def _docx(dados: bytes) -> str:
    from docx import Document
    from docx.text.paragraph import Paragraph

    doc = Document(io.BytesIO(dados))

    def conteudo(container):
        for bloco in container.iter_inner_content():
            if isinstance(bloco, Paragraph):
                if bloco.text.strip():
                    yield bloco.text
                continue
            # Células mescladas aparecem mais de uma vez na grade. Leia o
            # conteúdo de cada célula uma vez, inclusive tabelas internas.
            vistas = set()
            for linha in bloco.rows:
                celulas = []
                for celula in linha.cells:
                    if celula._tc in vistas:
                        continue
                    vistas.add(celula._tc)
                    texto = " ".join(conteudo(celula)).strip()
                    if texto:
                        celulas.append(texto)
                if celulas:
                    yield " ".join(celulas)

    paragrafos = list(conteudo(doc))
    return "\n".join(paragrafos)


def _pdf(dados: bytes) -> str:
    from pypdf import PdfReader
    leitor = PdfReader(io.BytesIO(dados))
    if leitor.is_encrypted and not leitor.decrypt(""):
        raise ArquivoNaoSuportado(
            "Este PDF está protegido por senha. Salve uma cópia sem senha "
            "para convertê-lo em áudio.")
    paginas = [(p.extract_text() or "") for p in leitor.pages]
    texto = "\n".join(paginas).strip()
    if not texto:
        raise ArquivoNaoSuportado(
            "Este PDF não tem texto selecionável (parece ser imagem "
            "escaneada). Faça OCR antes ou cole o texto.")
    return texto


def extrair_texto(nome: str, dados: bytes) -> str:
    sufixo = Path(nome).suffix.lower()
    if sufixo in (".txt", ".md", ".text"):
        return _texto_puro(dados)
    if sufixo == ".docx":
        return _docx(dados)
    if sufixo == ".pdf":
        return _pdf(dados)
    if sufixo == ".doc":
        raise ArquivoNaoSuportado(
            "Arquivos .doc antigos não são suportados. Salve como .docx.")
    raise ArquivoNaoSuportado(
        f"Formato '{sufixo or nome}' não suportado. Use .txt, .docx ou .pdf.")
