from polygon import RESTClient
from datetime import datetime, timedelta
from dateutil.relativedelta import *
from polygon import RESTClient
from polygon.rest import models
import requests
import pandas as pd
import altair as alt
import streamlit as st
import numpy as np
import math
from bs4 import BeautifulSoup
import aiohttp
import asyncio
import nest_asyncio
import plotly.express as px
nest_asyncio.apply()

key = st.secrets["polygon_key"]
DJIA = 'https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average'
SPY = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
QQQ = 'https://en.wikipedia.org/wiki/Nasdaq-100#Components'


def get_index_constituents():

    with requests.Session() as session:
        DJIA_info = session.get(DJIA)
        DJIA_soup = BeautifulSoup(DJIA_info.text, 'html.parser')
        SPY_info = session.get(SPY)
        SPY_soup = BeautifulSoup(SPY_info.text, 'html.parser')
        QQQ_info = session.get(QQQ)
        QQQ_soup = BeautifulSoup(QQQ_info.text, 'html.parser')

    ###DJIA
    html_table = DJIA_soup.find_all('table')[1]
    data = pd.read_html(html_table.prettify())
    DJIA_df = data[0]

    DJIA_df_upd = DJIA_df[['Company', 'Symbol', 'Industry']].copy()
    DJIA_df_upd = DJIA_df_upd.rename(columns={'Symbol': 'Ticker', 'Industry': 'GICS Sector'})
    DJIA_df_upd['GICS Sub-Industry'] = ""
    DJIA_df_upd['Index'] = 'DJIA'

    ###SPY
    html_table = SPY_soup.find_all('table')[0]
    data = pd.read_html(html_table.prettify())
    SPY_df = data[0]
    SPY_df_upd = SPY_df[['Security', 'Symbol', 'GICS  Sector', 'GICS Sub-Industry']].copy()
    SPY_df_upd = SPY_df_upd.rename(columns={'Security': 'Company', 'Symbol': 'Ticker', 'GICS  Sector': 'GICS Sector'})
    SPY_df_upd['Index'] = "SP500"

    ###QQQ
    html_table = QQQ_soup.find_all('table')[4]
    data = pd.read_html(html_table.prettify())
    QQQ_df = data[0]
    QQQ_df_upd = QQQ_df[['Company', 'Ticker', 'GICS  Sector', 'GICS  Sub-Industry']].copy()
    QQQ_df_upd = QQQ_df_upd.rename(columns={'GICS  Sector': 'GICS Sector', 'GICS  Sub-Industry': 'GICS Sub-Industry'})
    QQQ_df_upd['Index'] = "Nasdaq"

    index_list = []
    index_list.append(DJIA_df_upd)
    index_list.append(SPY_df_upd)
    index_list.append(QQQ_df_upd)

    index_df = pd.concat(index_list)
    index_df = index_df.reset_index()
    index_df = index_df.drop(columns = ['index'])

    return index_df

def get_delta(key):
    """
    Uses the All Ticker Endpoint to get price delta
    """
    
    ALL_TICKER = 'https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers?include_otc=false&apiKey={}'
    with requests.Session() as session:
        r = session.get(ALL_TICKER.format(key))
        data = r.json()
    ls = []

    for i in np.arange(len(data['tickers'])):
        ticker = data['tickers'][i]['ticker']
        delta = data['tickers'][i]['todaysChangePerc']
        dict1 = {'Ticker': ticker, 'Delta': delta}
        df = pd.DataFrame(dict1, index = [0])
        ls.append(df)

    all_tickers = pd.concat(ls)
    all_tickers = all_tickers.reset_index()
    all_tickers = all_tickers.drop(columns = ['index'])
    return all_tickers

results = []
async def mc_api_call(ticker_list, key):
    """
    Uses Async to loop through the reference details endpoint. Returns a Json response
    """
    REF_V3 = 'https://api.polygon.io/v3/reference/tickers/{}?apiKey={}'
    session = aiohttp.ClientSession()
    tasks = [session.get(REF_V3.format(ticker, key)) for ticker in ticker_list]
    responses = await asyncio.gather(*tasks)

    for response in responses:
        results.append(await response.json())
    await session.close()
    return results

def get_market_cap(ticker_list, key):
    loop = asyncio.get_event_loop()
    data = loop.run_until_complete(mc_api_call(ticker_list, key))

    list1 = []
    for i in np.arange(len(data)):
        ticker = data[i]['results']['ticker']
        market_cap = data[i]['results']['market_cap']

        dict1 = {'Ticker': ticker,
                'Market_cap': market_cap}
        
        df = pd.DataFrame(dict1, index = [0])
        list1.append(df)

    market_cap_df = pd.concat(list1)
    market_cap_df.reset_index()
    return market_cap_df

def get_heat_map_data():
    index_df = get_index_constituents()
    ticker_list = index_df['Ticker'].to_list()
    delta_df = get_delta(key)
    market_cap_df = get_market_cap(ticker_list, key)
    color_bin = [-100,-2,-1,0, 1, 2,100]

    heat_map_df = index_df.merge(delta_df, on ='Ticker', how='left')
    heat_map_df = heat_map_df.merge(market_cap_df, on ='Ticker', how='left')
    heat_map_df['Colors'] = pd.cut(heat_map_df['Delta'], bins=color_bin, labels=['red','indianred', 'lightpink', 'lightgreen', 'lime', 'green'])
    return heat_map_df

def create_heat_map(indx):
    """
    Either input DJIA, SP500, Nasdaq as indx
    """
    heat_map_df = get_heat_map_data()
    heat_map_df = heat_map_df[heat_map_df['Index'] == indx]

    fig = px.treemap(heat_map_df, path=[px.Constant("all"), 'GICS Sector','Ticker'], values = 'Market_cap', color='Colors',
                 color_discrete_map ={'(?)':'#262931', 'red':'red', 'indianred':'indianred','lightpink':'lightpink', 'lightgreen':'lightgreen','lime':'lime','green':'green'},

                hover_data = {'Delta':':.2p'}
                )
    #fig.show()
    return fig

def display_webapp():
    st.set_page_config(page_title="Dashboard", page_icon="👋")
    st.write("Market Overview")
    st.sidebar.success("Select a demo above.")
    st.plotly_chart(create_heat_map("SP500"))
    return None

display_webapp()
