# Texto em Áudio

> **Parte da suíte Holly**  
> Ferramentas local-first para texto, documentos e mídia, com privacidade por padrão e segurança verificável.  
> [HollyOCR](https://github.com/HollyGM/HollyOCR) · [HollyCorretor](https://github.com/HollyGM/HollyCorretor) · [HollyTranscrição](https://github.com/HollyGM/HollyTranscricao) · [HollyOptimizer](https://github.com/HollyGM/HollyOptimizer)

Transforma petições e textos de sustentação oral em **MP3 com leitura natural em português do Brasil**.

Não é só "texto para voz": antes de falar, o programa reescreve o texto do jeito que um advogado o diria em voz alta. `art. 5º, § 1º` vira "artigo quinto, parágrafo primeiro"; `Lei nº 8.078/90` vira "Lei número oito mil e setenta e oito, de mil novecentos e noventa"; `R$ 10.000,00 (dez mil reais)` é lido uma vez só.

Diferente das outras ferramentas da suíte, a voz vem de um serviço online: **o texto sai do computador**. Leia [Sigilo](#limites-que-você-precisa-conhecer) antes de usar com peças sigilosas.

## Como usar

**Aplicativo para Mac (recomendado):** abra **Texto em Áudio** na pasta **Aplicativos**. A versão 1.1.0 tem janela própria, menus e ícone e incorpora Python, as dependências e as ferramentas de áudio. A síntese de voz exige internet. Você pode arrastar o aplicativo para o Dock.

Os MP3s do aplicativo ficam em `~/Music/Texto em Áudio/` (pasta Música). O menu **Arquivo → Abrir Pasta dos MP3** abre essa pasta. As pronúncias e preferências ficam em `~/Library/Application Support/Texto em Áudio/`; o texto das peças não é salvo nas preferências. **Arquivo → Editar Pronúncias** abre o arquivo de pronúncias, e **Exibir → Abrir Registro do Aplicativo** mostra o log em `~/Library/Logs/Texto em Áudio/`. Fechar o aplicativo encerra o servidor local; se houver uma conversão em andamento, o aplicativo pergunta antes de interrompê-la.

**Pela interface no navegador:** dê duplo clique em `iniciar.command`. Na primeira vez ele cria o ambiente `.venv` e instala as dependências; depois abre o navegador em `http://127.0.0.1:8765`. Esse modo usa Python e ffmpeg instalados no computador.

1. Cole o texto ou envie um arquivo `.docx`, `.pdf` ou `.txt`.
2. Escolha a voz e a velocidade. **Ouvir amostra** toca uma frase de teste.
3. Se tiver um tempo de tribuna (ex.: 15 min), digite-o: o programa diz se o texto cabe e, se não couber, qual velocidade resolve.
4. Abra **Ver como o texto será lido** e confira números, siglas e expressões latinas.
5. **Gerar MP3**. No aplicativo, o arquivo fica na pasta Música → Texto em Áudio; na execução pelo código, na pasta `saidas/`. A interface mostra o caminho completo.

**Pela linha de comando:**

```bash
.venv/bin/python -m texto_audio gerar minha-peca.docx --velocidade 10 --omitir-referencias
```

Opções: `--voz`, `--velocidade` (-50 a 100, em %), `--pausa` (ms entre parágrafos), `--siglas extenso|letras`, `--omitir-referencias`, `--sem-normalizar-volume`, `--titulo`, `-o`/`--saida` (pasta de destino; padrão `saidas/`).

## O que a normalização faz

| Texto | Leitura |
|---|---|
| `art. 5º, inciso XXXV, da CF/88` | artigo quinto, inciso trinta e cinco, da Constituição Federal de mil novecentos e oitenta e oito |
| `art. 1.015, § 1º, do CPC` | artigo mil e quinze, parágrafo primeiro, do Código de Processo Civil |
| `Processo nº 1234567-89.2023.8.26.0100` | número lido dígito a dígito, em grupos |
| `10/03/2024`, `14h30`, `1,5%` | dez de março de dois mil e vinte e quatro, catorze horas e trinta minutos, um vírgula cinco por cento |
| `R$ 10.000,00 (dez mil reais)` | dez mil reais |
| `REsp 1.234.567/SP`, `TJSP`, `TRF3` | Recurso Especial …, de São Paulo; Tribunal de Justiça de São Paulo; Tribunal Regional Federal da terceira Região |
| `Exmo. Sr. Dr.`, `fls.`, `c/c`, `e/ou` | Excelentíssimo Senhor Doutor, folhas, combinado com, e ou |
| `data venia`, `caput`, `habeas corpus` | respelling para a voz falar como um advogado brasileiro |
| `EXCELENTÍSSIMO SENHOR…` (título em caixa alta) | minúsculas (a voz soletraria "DO", "DA") |
| quebras de linha de PDF, links, `**markdown**` | limpos |

As regras ficam em `texto_audio/normalizar.py` (lógica) e `texto_audio/dados.py` (abreviações, siglas, expressões latinas). Estão cobertas por testes em `tests/test_normalizar.py`.

### Corrigindo uma pronúncia

Se a voz falar algo errado, edite `pronuncias.txt` (no aplicativo, por **Arquivo → Editar Pronúncias**) ou use a caixa "Pronúncias personalizadas" na interface. As preferências de pronúncia são lembradas nas próximas aberturas. Uma por linha:

```
BNDES = bê ene dê é ésse
Fulano de Tal = Fulâno de Tal
```

Os respellings de latim em `dados.py` (`PRONUNCIAS_PADRAO`, como "cápute" para *caput*) foram escritos de memória e **ninguém os ouviu ainda**: gere uma amostra, ouça e ajuste o que não soar bem.

## Limites que você precisa conhecer

- **Sigilo.** A voz vem do serviço online de voz neural da Microsoft (biblioteca `edge-tts`), e **o texto é enviado a esses servidores**. Não use, como está, para peças sob segredo de justiça ou com dados sensíveis. O restante (normalização, montagem do MP3, interface) roda só neste computador, e o servidor escuta apenas em `127.0.0.1`. Para trocar por um motor local ou por uma API contratada (Azure, Google, OpenAI, ElevenLabs, Piper), escreva uma classe com o método `sintetizar` em `texto_audio/motores.py`: o resto do programa não muda.
- **Serviço não oficial.** O `edge-tts` usa o recurso "ler em voz alta" do Edge sem chave de API; a Microsoft pode alterá-lo ou limitá-lo a qualquer momento.
- **Estimativa de duração** é aproximada: errou cerca de 2% nos dois textos usados para calibrá-la, e em outros textos pode variar mais. A duração real aparece depois de gerar.
- **PDF escaneado** (imagem) não tem texto: faça OCR antes. **`.doc` antigo** não é lido: salve como `.docx`.
- **MP3 final:** mono, 24 kHz, 64 kbps (o suficiente para voz; ~0,5 MB por minuto), com volume igualado em -16 LUFS.

## Requisitos e testes

Python 3.10 ou mais novo (testado na 3.14) e `ffmpeg` (`brew install ffmpeg`).
Esses requisitos se aplicam à execução e construção pelo código; o aplicativo instalado já os incorpora. O pacote criado é para Macs com Apple Silicon.

```bash
python3 -m venv .venv            # se ainda não existir (o iniciar.command também cria)
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests -q
```

Os testes não usam a rede (a voz é substituída por um motor falso).

### Atualização 1.1.0

- Corrige valores sem separador de milhares, como `R$ 1000,00`, e mantém valores por extenso divergentes para conferência.
- Lê tabelas do Word na posição em que aparecem, sem repetir células mescladas; aceita TXT UTF-16/UTF-32 e explica PDFs protegidos por senha.
- Organiza as conversões em fila, preserva tarefas ativas e retoma o acompanhamento após falhas de conexão ou recarregamento.
- Impede sobrescrita de MP3s com o mesmo título, grava somente arquivos completos e encerra subprocessos ao cancelar.
- Restringe acesso ao servidor local e evita que um upload atrasado substitua edições recentes do texto.

### Reconstruir o aplicativo

Em macOS com as ferramentas de linha de comando da Apple:

```bash
.venv/bin/python -m pip install -r requirements-build.txt
.venv/bin/python macos/construir.py --instalar
.venv/bin/python macos/verificar.py "/Applications/Texto em Áudio.app" --online
```

Sem `--instalar`, o aplicativo fica em `dist/Texto em Áudio.app`. Com `--instalar`, ele é copiado para `/Applications` (ou `~/Applications`, se não houver permissão), e a versão anterior é renomeada para `Texto em Áudio - anterior.app`; se esse backup já existir, a instalação para. `requirements-lock.txt` registra as versões de execução usadas neste pacote. O teste `--online` envia apenas uma frase genérica de teste e verifica a voz, a montagem e o download de um MP3 temporário. O aplicativo recebe assinatura local; a distribuição pública exigiria assinatura e notarização próprias. O empacotamento segue a [documentação do PyInstaller](https://pyinstaller.org/en/stable/usage.html).

Se o ffmpeg do Homebrew estiver temporariamente quebrado por uma atualização de dependências, a construção aceita `--ffmpeg-dir PASTA` com binários funcionais e suas bibliotecas. O aplicativo instalado usa suas próprias cópias.

## Estrutura

```
texto_audio/
  normalizar.py   texto jurídico -> texto falado
  dados.py        abreviações, siglas, latim, estados
  blocos.py       divide em trechos e define as pausas
  motores.py      motor de voz (edge-tts); ponto de troca de provedor
  audio.py        ffmpeg: apara silêncio, junta, iguala volume
  pipeline.py     orquestra tudo e reporta progresso
  extrair.py      lê .txt, .docx e .pdf
  servidor.py     API local (FastAPI)
  __main__.py     linha de comando
  caminhos.py     recursos e diretórios graváveis do aplicativo
macos/
  App.swift       janela nativa (WebKit), menus e ciclo de vida do servidor
  backend.py      servidor incorporado ao aplicativo
  construir.py    empacotamento (PyInstaller + swiftc) e instalação
  verificar.py    teste do aplicativo empacotado
  icone.swift     gera o ícone
web/index.html    interface
tests/            testes (pytest, sem rede)
iniciar.command   abre a interface no navegador pelo código
pronuncias.txt    correções de pronúncia padrão (o aplicativo copia para Application Support)
saidas/           MP3 gerados pelo código (criada automaticamente; fora do git)
```
