"""Dicionários de leitura para texto jurídico em pt-BR.

Tudo aqui é dado puro (sem lógica), para ser fácil de ampliar. Se uma sigla ou
expressão sair com pronúncia estranha, acrescente-a aqui ou no arquivo
`pronuncias.txt` da raiz do projeto (formato: `termo = leitura`).
"""

# Abreviações com ponto. Chave em minúsculas; o normalizador preserva a
# capitalização inicial ("Exmo." -> "Excelentíssimo").
ABREVIACOES = {
    "exmo": "excelentíssimo",
    "exma": "excelentíssima",
    "exmos": "excelentíssimos",
    "exmas": "excelentíssimas",
    "ilmo": "ilustríssimo",
    "ilma": "ilustríssima",
    "sr": "senhor",
    "sra": "senhora",
    "srs": "senhores",
    "sras": "senhoras",
    "dr": "doutor",
    "dra": "doutora",
    "drs": "doutores",
    "profa": "professora",
    "prof": "professor",
    "min": "ministro",
    "des": "desembargador",
    "desa": "desembargadora",
    "dep": "deputado",
    "rel": "relator",
    "adv": "advogado",
    "fls": "folhas",
    "fl": "folha",
    "pp": "páginas",
    "cf": "conforme",
    "etc": "et cétera",
    "inc": "inciso",
    "incs": "incisos",
    "arts": "artigos",
    "art": "artigo",
    "parág": "parágrafo",
    "ss": "seguintes",
    "obs": "observação",
    "tel": "telefone",
    "av": "avenida",
    "pág": "página",
    "págs": "páginas",
    "núm": "número",
}

# Abreviações que só valem em contexto (para não trocar "p." de uma frase
# qualquer). Tratadas por regex própria no normalizador.
#   p. <número>   -> página
#   al. <letra>   -> alínea

# Siglas processuais: sempre expandidas (faladas por extenso).
PECAS_E_RECURSOS = {
    "REsp": "Recurso Especial",
    "AREsp": "Agravo em Recurso Especial",
    "EREsp": "Embargos de Divergência em Recurso Especial",
    "AgRg": "Agravo Regimental",
    "AgInt": "Agravo Interno",
    "EDcl": "Embargos de Declaração",
    "HC": "Habeas Corpus",
    "RHC": "Recurso em Habeas Corpus",
    "ADI": "Ação Direta de Inconstitucionalidade",
    "ADC": "Ação Declaratória de Constitucionalidade",
    "ADPF": "Arguição de Descumprimento de Preceito Fundamental",
    "Rcl": "Reclamação",
    "ADO": "Ação Direta de Inconstitucionalidade por Omissão",
    "IRDR": "Incidente de Resolução de Demandas Repetitivas",
    "IAC": "Incidente de Assunção de Competência",
}

# Siglas institucionais e normativas. No modo "extenso" são lidas por extenso;
# no modo "letras" são soletradas ("S T F").
SIGLAS = {
    "TJ": "Tribunal de Justiça",
    "TRF": "Tribunal Regional Federal",
    "TRT": "Tribunal Regional do Trabalho",
    "TRE": "Tribunal Regional Eleitoral",
    "STF": "Supremo Tribunal Federal",
    "STJ": "Superior Tribunal de Justiça",
    "TST": "Tribunal Superior do Trabalho",
    "TSE": "Tribunal Superior Eleitoral",
    "STM": "Superior Tribunal Militar",
    "CNJ": "Conselho Nacional de Justiça",
    "CNMP": "Conselho Nacional do Ministério Público",
    "MP": "Ministério Público",
    "MPF": "Ministério Público Federal",
    "MPT": "Ministério Público do Trabalho",
    "PGR": "Procuradoria-Geral da República",
    "AGU": "Advocacia-Geral da União",
    "DPU": "Defensoria Pública da União",
    "OAB": "Ordem dos Advogados do Brasil",
    "CPC": "Código de Processo Civil",
    "CPP": "Código de Processo Penal",
    "CP": "Código Penal",
    "CC": "Código Civil",
    "CF": "Constituição Federal",
    "CRFB": "Constituição da República Federativa do Brasil",
    "CDC": "Código de Defesa do Consumidor",
    "CLT": "Consolidação das Leis do Trabalho",
    "CTN": "Código Tributário Nacional",
    "CTB": "Código de Trânsito Brasileiro",
    "ECA": "Estatuto da Criança e do Adolescente",
    "LINDB": "Lei de Introdução às Normas do Direito Brasileiro",
    "LEP": "Lei de Execução Penal",
    "LGPD": "Lei Geral de Proteção de Dados",
    "LRF": "Lei de Responsabilidade Fiscal",
    "LC": "Lei Complementar",
    "INSS": "Instituto Nacional do Seguro Social",
    "FGTS": "Fundo de Garantia do Tempo de Serviço",
    "CEF": "Caixa Econômica Federal",
    "DJe": "Diário da Justiça eletrônico",
    "DJ": "Diário da Justiça",
    "IPTU": "Imposto Predial e Territorial Urbano",
    "ICMS": "Imposto sobre Circulação de Mercadorias e Serviços",
    "IRPF": "Imposto de Renda da Pessoa Física",
    "IRPJ": "Imposto de Renda da Pessoa Jurídica",
    "ISS": "Imposto sobre Serviços",
    "IPI": "Imposto sobre Produtos Industrializados",
}

# Siglas que o TTS já fala bem como letras e que não convém expandir
# (ficam fora dos dois modos): CPF, CNPJ mantêm leitura em letras sempre.
SIGLAS_SEMPRE_LETRAS = {"CPF", "CNPJ", "RG", "CEP"}

# Só viram extenso quando vêm antes de um número ("RE 123", "MP 1.045/21"),
# porque sozinhas são ambíguas (MS = Mato Grosso do Sul, MP = Ministério Público).
SIGLAS_SO_COM_NUMERO = {
    "RE": "Recurso Extraordinário",
    "ARE": "Agravo em Recurso Extraordinário",
    "MS": "Mandado de Segurança",
    "RMS": "Recurso em Mandado de Segurança",
    "MP": "Medida Provisória",
    "EC": "Emenda Constitucional",
    "DL": "Decreto-Lei",
    "AI": "Agravo de Instrumento",
}

ESTADOS = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas",
    "BA": "Bahia", "CE": "Ceará", "DF": "Distrito Federal",
    "ES": "Espírito Santo", "GO": "Goiás", "MA": "Maranhão",
    "MT": "Mato Grosso", "MS": "Mato Grosso do Sul", "MG": "Minas Gerais",
    "PA": "Pará", "PB": "Paraíba", "PR": "Paraná", "PE": "Pernambuco",
    "PI": "Piauí", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte",
    "RS": "Rio Grande do Sul", "RO": "Rondônia", "RR": "Roraima",
    "SC": "Santa Catarina", "SP": "São Paulo", "SE": "Sergipe",
    "TO": "Tocantins",
}

MESES = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
    "agosto", "setembro", "outubro", "novembro", "dezembro",
]

# Expressões latinas e jargão: grafia -> respelling que uma voz pt-BR lê como
# um advogado brasileiro falaria. Comparação sem diferenciar maiúsculas.
PRONUNCIAS_PADRAO = {
    "data venia": "dáta vênia",
    "data máxima venia": "dáta máxima vênia",
    "habeas corpus": "rábeas córpus",
    "habeas data": "rábeas dáta",
    "caput": "cápute",
    "ex officio": "éks ofício",
    "in dubio pro reo": "in dúbio pro réu",
    "in dubio pro societate": "in dúbio pro sociedáte",
    "periculum in mora": "perículum in móra",
    "fumus boni iuris": "fúmus bóni iúris",
    "fumus boni juris": "fúmus bóni iúris",
    "erga omnes": "érga ômnes",
    "inter partes": "ínter pártes",
    "ultra petita": "últra petíta",
    "extra petita": "êxtra petíta",
    "citra petita": "cítra petíta",
    "infra petita": "ínfra petíta",
    "in limine": "in límine",
    "inaudita altera pars": "inaudíta áltera pars",
    "sub judice": "sub iudíce",
    "ipsis litteris": "ípsis lítteris",
    "mutatis mutandis": "mutátis mutándis",
    "pari passu": "pári pássu",
    "lato sensu": "láto sénsu",
    "stricto sensu": "estrícto sénsu",
    "de cujus": "de cújus",
    "ex nunc": "éks núnki",
    "ex tunc": "éks túnki",
    "in casu": "in cázu",
    "prima facie": "príma fácie",
    "sine qua non": "sine kuá nón",
    "a quo": "a kuó",
    "ad quem": "ad kuém",
    "ad causam": "ad cáusam",
    "ad processum": "ad procéssum",
    "in re ipsa": "in rê ípsa",
    "onus probandi": "ônus probándi",
    "status quo": "estátus kuó",
    "amicus curiae": "amícus cúrie",
    "ratio decidendi": "rácio decidéndi",
    "obiter dictum": "óbiter díctum",
    "non bis in idem": "nón bis in ídem",
}
