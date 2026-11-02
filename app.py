"""Painel de fermentação. Execute: streamlit run app.py"""
from io import BytesIO
from html import escape
import re
import unicodedata
import pandas as pd

PARES = {
    'vinho bruto': {'celulas vivas': 'Células Vivas', 'bastonetes': 'Bastonetes'},
    'mosto': {'acidez': 'Acidez', 'ph': 'pH'},
    'vinho centrifugado': {'acidez': 'Acidez', 'ph': 'pH'},
}
NOMES = {'vinho bruto': 'Vinho Bruto', 'mosto': 'Mosto',
         'vinho centrifugado': 'Vinho Centrifugado'}
CSS = """:root {color-scheme:light} * {box-sizing:border-box}
body {font-family:Arial,sans-serif;background:#f1f5f4;color:#17302e;margin:0;padding:28px}
.wrap{max-width:1200px;margin:auto} .hero{background:#103f36;color:white;padding:26px;border-radius:14px}
.hero h1{margin:6px 0 12px;font-size:28px}.eyebrow{font-size:12px;letter-spacing:2px}
.date{display:inline-block;background:#d9eea5;color:#163d31;padding:12px 18px;border-radius:8px;font-size:23px;font-weight:bold}
.meta{margin-top:14px;font-size:14px}.section{background:white;padding:22px;border-radius:12px;margin-top:18px;border:1px solid #dae5df}
h2{font-size:20px;margin-top:0} .scroll{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:14px}th{background:#e7efeb;text-align:left;color:#164a3c}
th,td{padding:13px 12px;border-bottom:1px solid #e3ebe6;white-space:nowrap}
tbody tr:nth-child(even){background:#f7faf8} .note{color:#50645b;font-size:13px;line-height:1.6}
button{background:#174f40;color:white;padding:12px 20px;border:0;border-radius:7px;cursor:pointer}
@media(max-width:650px){body{padding:12px}.hero{padding:20px}.hero h1{font-size:23px}.section{padding:15px}}
@media print{body{background:white;padding:0}.section,.hero{break-inside:avoid}.no-print{display:none}table{font-size:11px}th,td{padding:8px}.scroll{overflow:visible}}
"""

def normalizar(valor):
    texto = unicodedata.normalize('NFKD', str(valor))
    return ' '.join(''.join(c for c in texto if not unicodedata.combining(c)).lower().split())

def preparar(df):
    """Seleciona apenas as seis combinações solicitadas, sem alterar os valores."""
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    obrigatorias = ['Material', 'Equipamento', 'Característica', 'Dt. Resultado', 'Vl. Resultado']
    faltam = [c for c in obrigatorias if c not in df.columns]
    if faltam:
        raise ValueError('Colunas ausentes: ' + ', '.join(faltam))
    df['_material'] = df['Material'].map(normalizar)
    df['_caract'] = df['Característica'].map(normalizar)
    mascara = pd.Series([c in PARES.get(m, {}) for m, c in zip(df['_material'], df['_caract'])], index=df.index, dtype=bool)
    df = df.loc[mascara].copy()
    if df.empty:
        return df
    df['Material'] = df['_material'].map(NOMES)
    df['Característica'] = df.apply(lambda r: PARES[r['_material']][r['_caract']], axis=1)
    df['_data'] = pd.to_datetime(df['Dt. Resultado'], dayfirst=True, errors='coerce')
    df['_registro'] = pd.to_datetime(df.get('Dt. Registro', pd.Series(pd.NaT, index=df.index)), dayfirst=True, errors='coerce')
    for c in ['Equipamento', 'Local', 'Tipo de Análise']:
        if c not in df:
            df[c] = ''
        df[c] = df[c].fillna('').astype(str).str.strip()
    df['_dorna'] = df['Equipamento'].map(lambda x: re.fullmatch(r'dorna\s*0?([1-6])', normalizar(x)))
    df['_dorna'] = df['_dorna'].map(lambda x: int(x.group(1)) if x else 0)
    return df

def formatar(valor):
    if pd.isna(valor):
        return 'Sem resultado'
    if isinstance(valor, str):
        return valor
    texto = f'{valor:,.6f}'.rstrip('0').rstrip('.')
    return texto.replace(',', '@').replace('.', ',').replace('@', '.')

def data_hora(valor):
    return valor.strftime('%d/%m/%Y %H:%M') if pd.notna(valor) else 'Sem data válida'

def exponencial(valor):
    if pd.isna(valor):
        return 'Sem resultado'
    try:
        if isinstance(valor, str):
            valor = float(valor.strip().replace('.', '').replace(',', '.')) if ',' in valor else float(valor)
        mantissa, expoente = f'{valor:.2e}'.split('e')
        sobrescrito = str(int(expoente)).translate(str.maketrans('-0123456789', '⁻⁰¹²³⁴⁵⁶⁷⁸⁹'))
        return f'{mantissa.replace(".", ",")} × 10{sobrescrito}'
    except (ValueError, TypeError):
        return str(valor)

def tabelas(dia):
    # Desempate: data do resultado, depois registro e ordem original da planilha.
    ordenado = dia.sort_values(['_data', '_registro'], kind='stable', na_position='first')
    vinho = ordenado[(ordenado['Material'] == 'Vinho Bruto') & (ordenado['_dorna'] > 0)]
    ultimos = vinho.drop_duplicates(['_dorna', 'Característica'], keep='last')
    linhas = []
    for n in range(1, 7):
        registros = ultimos[ultimos['_dorna'] == n]
        linha = {'Data': registros['_data'].max().strftime('%d/%m/%Y') if len(registros) else '—',
                 'Dorna': f'Dorna {n}'}
        for caract in ['Células Vivas', 'Bastonetes']:
            r = ultimos[(ultimos['_dorna'] == n) & (ultimos['Característica'] == caract)]
            coluna = 'Células vivas (%)' if caract == 'Células Vivas' else 'Bastonetes'
            formato = exponencial if caract == 'Bastonetes' else formatar
            linha[coluna] = formato(r.iloc[-1]['Vl. Resultado']) if len(r) else 'Sem resultado'
        linhas.append(linha)
    outras = ordenado[ordenado['Material'] != 'Vinho Bruto'].copy()
    chaves = ['Material', 'Equipamento', 'Local', 'Tipo de Análise', 'Característica']
    outras = outras.drop_duplicates(chaves, keep='last')
    def detalhes(frame):
        frame = frame.sort_values(['_data', 'Material', 'Equipamento', 'Característica'])
        saida = frame[['Material', 'Característica']].copy()
        saida['Resultado'] = frame['Vl. Resultado'].map(formatar)
        saida.insert(0, 'Data / hora do resultado', frame['_data'].map(data_hora))
        return saida.reset_index(drop=True)
    itens = [('Vinho Bruto · seis dornas', pd.DataFrame(linhas)),
             ('Mosto e Vinho Centrifugado · últimos resultados do dia', detalhes(outras))]
    return itens

def gerar_html(itens, data):
    secoes = ''.join('<section class="section"><h2>' + escape(titulo) + '</h2><div class="scroll">'
                     + tabela.to_html(index=False, escape=True, border=0) + '</div></section>'
                     for titulo, tabela in itens)
    return f'''<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Resultados da fermentação · {data:%d/%m/%Y}</title><style>{CSS}</style></head>
    <body><main class="wrap"><header class="hero"><div class="eyebrow">LABORATÓRIO INDUSTRIAL</div>
    <h1>Monitor de resultados · Fermentação</h1><div class="date">DATA DOS RESULTADOS: {data:%d/%m/%Y}</div>
    </header>
    {secoes}<p class="no-print"><button onclick="window.print()">Imprimir / Salvar PDF</button></p>
    </main></body></html>'''

def main():
    import streamlit as st
    import streamlit.components.v1 as components
    st.set_page_config(page_title='Fermentação | Resultados', page_icon='🧪', layout='wide')
    st.title('Monitor de resultados · Fermentação')
    st.caption('Vinho Bruto • Mosto • Vinho Centrifugado')
    arquivo = st.sidebar.file_uploader('Carregar Monitor de Digitação (.xlsx)', type=['xlsx'])
    if arquivo is None:
        st.info('Carregue a planilha do Monitor de Digitação para visualizar os resultados.')
        st.stop()

    @st.cache_data(show_spinner=False)
    def ler_planilha(conteudo, aba):
        return preparar(pd.read_excel(BytesIO(conteudo), sheet_name=aba, engine='openpyxl'))

    try:
        conteudo = arquivo.getvalue()
        with pd.ExcelFile(BytesIO(conteudo), engine='openpyxl') as livro:
            abas = livro.sheet_names
        aba = 'SAP Document Export' if 'SAP Document Export' in abas else abas[0]
        dados = ler_planilha(conteudo, aba)
    except Exception as erro:
        st.error(f'Não foi possível ler a planilha: {erro}')
        st.stop()
    if dados.empty:
        st.warning('Nenhum registro das análises solicitadas foi encontrado nesta aba.')
        st.stop()
    invalidas = int(dados['_data'].isna().sum())
    if invalidas:
        st.warning(f'{invalidas} registro(s) com data de resultado inválida foram excluídos do painel.')
    dados = dados[dados['_data'].notna()].copy()
    if dados.empty:
        st.error('Não há resultados com data válida para exibir.')
        st.stop()
    data = dados['_data'].dt.date.max()
    dia = dados[dados['_data'].dt.date == data]
    nao_identificadas = dia[(dia.Material == 'Vinho Bruto') & (dia['_dorna'] == 0)]
    if len(nao_identificadas):
        st.warning(f'{len(nao_identificadas)} registro(s) de Vinho Bruto sem identificação Dorna 1 a 6 não aparecem na tabela de dornas.')
    itens = tabelas(dia)
    html = gerar_html(itens, data)
    st.download_button('⬇ Gerar e baixar HTML', data=html.encode('utf-8'),
                       file_name=f'resultados_fermentacao_{data:%Y-%m-%d}.html', mime='text/html')
    components.html(html, height=1000, scrolling=True)

if __name__ == '__main__':
    main()
