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
from newsapi import NewsApiClient
from GoogleNews import GoogleNews
import newspaper
import nltk
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas_ta as ta
from numerize import numerize

key = st.secrets["polygon_key"]
POLYGON_TICKER_DETAILS_V3 = 'https://api.polygon.io/v3/reference/tickers/{}?apiKey={}'
POLYGON_TICKER_NEWS = 'https://api.polygon.io/v2/reference/news?ticker={}&limit=100&apiKey={}'

def get_aggregates(stock, st_date, en_date):
    """
    Uses Polygon.io RestClient API to retrieve aggregates data for a single stock
    """

    client = RESTClient(key)
    Data  = pd.DataFrame(columns = ['active', 'currency_name', 'currency_symbol', 'ticker', 'timestamp'])

    Aggs = []
    for a in client.list_aggs(stock, 1, "day", st_date, en_date, limit=50000):
      o = a.open
      h = a.high
      l = a.low
      c = a.close
      v = a.volume
      ts = datetime.fromtimestamp(a.timestamp/1000)
      vwap = a.vwap
      transactions = a.transactions

      data = {'open': o,
              'high': h,
              'low': l,
              'close': c,
              'volume': v,
              'vwap': vwap,
              'transactions': transactions,
              'date': ts}

      AggData = pd.DataFrame(data, index=[0])
      Aggs.append(AggData)

    AggData = pd.concat(Aggs)
    AggData = AggData.set_index("date")
    AggData['daily_return'] = AggData['close'].pct_change()
    AggData['cumulative_ret'] = (1 + AggData['daily_return']).cumprod() - 1

    return AggData

def get_ref_data(stock):
    """
    Makes Polygon.io API call to retreive reference data
    """
    session = requests.Session()
    r = session.get(POLYGON_TICKER_DETAILS_V3.format(stock, key))
    data = r.json()

    try:
        comp_name = data['results']['name']
        market_cap = data['results']['market_cap']
        description = data['results']['description']
        homepage_url = data['results']['homepage_url']
        currency = data['results']['currency_name']
        sic_code = data['results']['sic_code']
        total_employees = data['results']['total_employees']
        weighted_shares_outstanding = data['results']['weighted_shares_outstanding']

        return comp_name, market_cap, description, homepage_url, total_employees, currency, weighted_shares_outstanding

    except:
        comp_name = data['results']['name']
        return comp_name

def get_financial_data(stock):
    """
    Makes Polygon.io API call to retreive financial data
    """
    session = requests.Session()
    r = session.get(POLYGON_FINANCIALS.format(stock, key))
    data = r.json()
    eps = data['results'][0]['financials']['income_statement']['diluted_earnings_per_share']['value']
    return eps

def create_chart(agg_data):
    """
    Uses plotly to create chart
    """

    df = agg_data.reset_index()
    sma_50 = df.ta.sma(length=50) #sma
    sma_100 = df.ta.sma(length=100)
    bbands = df.ta.bbands()
    rsi = df.ta.rsi()
    st_date = datetime.now() - relativedelta(years=+1)
    en_date = datetime.now()

    fig = make_subplots(rows=3, cols=1,
                        shared_xaxes=True,
                        row_heights = [0.6, 0.2, 0.2],
                        subplot_titles=("Price", "Volume", "RSI"))

    fig.add_trace(go.Scatter(x=df['date'],
                            y=df['close'],
                            fill='tozeroy', # fill down to xaxis
                            name= 'price',
                            marker_color = "rgb(66, 166, 93)"
                            ),row=1, col=1)

    fig.add_trace(
        go.Scatter(
            x=df['date'],
            y=sma_50,
            line = dict(color="#e0e0e0"),
            name = "sma_50",
            visible='legendonly'
        ))

    fig.add_trace(
        go.Scatter(
            x=df['date'],
            y=sma_100,
            line = dict(color="#e0e0e0"),
            name = "sma_100",
            visible='legendonly'
        ))

    fig.add_trace(
        go.Scatter(
            x=df['date'],
            y=bbands['BBL_5_2.0'],
            line = dict(color="#e0e0e0"),
            name = "BBL",
            visible='legendonly'
        ))

    fig.add_trace(
        go.Scatter(
            x=df['date'],
            y=bbands['BBM_5_2.0'],
            line = dict(color="#e0e0e0"),
            name = "BBM",
            visible='legendonly'
        ))

    fig.add_trace(
        go.Scatter(
            x=df['date'],
            y=bbands['BBU_5_2.0'],
            line = dict(color="#e0e0e0"),
            name = "BBU",
            visible='legendonly'
        ))

    fig.add_hline(y=df['close'].iloc[-1], line_dash="dash", line_width=0.5)

    fig.add_trace(
        go.Bar(
            x=df['date'],
            y=df['volume'],
            name = "volume",
            marker_color = "rgb(66, 166, 93)",
            xperiod = "M1"
        ),row=2, col=1)

    fig.add_trace(
        go.Scatter(
            x=df['date'],
            y=rsi,
            name = "RSI",
            marker_color = "rgb(66, 166, 93)"
        ),row=3, col=1)

    fig.update_layout(xaxis_rangeslider_visible=False,
                      xaxis_rangeselector_font_color='white',
                      xaxis_rangeselector_y=1.10,
                      template = 'plotly_dark',
                      width=800,
                      height=600,
                      xaxis=dict(
                          rangeselector=dict(
                          buttons=list([
                          dict(count=1, label="1m", step="month", stepmode="backward" ),
                          dict(count=6, label="6m", step="month", stepmode="backward"),
                          dict(count=1, label="YTD", step="year", stepmode="todate"),
                          dict(count=1, label="1y", step="year", stepmode="backward"),
                          dict(count=5, label="5y", step="year", stepmode="backward")
                      ]))),
                      yaxis=dict(
                          autorange=True,
                          fixedrange=True,
                      )
                      )

    fig.update_annotations(xshift=-320)

    fig.update_xaxes(
        rangebreaks=[
            dict(bounds=["sat", "mon"]), #hide weekends
        ])

    return fig

def display_webapp():
    fr_date = (datetime.now() - relativedelta(years=+5)).strftime("%Y-%m-%d")
    to_date = datetime.now().strftime("%Y-%m-%d")

    st.set_page_config(page_title="stock chart", page_icon="📈")

    with st.sidebar:
        #Ticker Options
        stock = st.text_input('Stock Ticker', 'AAPL')
        agg_data = get_aggregates(stock, fr_date, to_date)

        try:
            comp_name, market_cap, description, homepage_url, total_employees, currency, weighted_shares_outstanding = get_ref_data(stock)
        except:
            comp_name = get_ref_data(stock)
        
        st.write("Security: " + comp_name)
        st.divider()
        
        try:
            st.write("Market Cap: " + f"{numerize.numerize(market_cap)} " + f"{currency.upper()}")
            st.divider()
        except:
            st.write("")
        #eps = get_financial_data(stock)
        #st.subheader("P/E Ratio: " + f"{agg_data['close'].iloc[-1]/ eps}")
        try:
            st.write("Number of Employees: " + f"{numerize.numerize(total_employees)}")
            st.divider()
        except:
            st.write("")
            
        try:
            with st.expander("Company Description"):
                st.write(description)
        except:
            st.write("")

    st.header(f"{stock}" + " - " + str(round(agg_data['close'][-1],2)))
    price_difference_day, price_difference_yoy, week_high, week_low = st.columns(4)
    price_difference_day.metric(
                    label = "Price difference (day)",
                    value = "$" + str(round(agg_data['close'].diff(periods = 1)[-1], 2)),
                    delta = str(round(agg_data['close'].pct_change(periods = 1)[-1]*100, 2)) + "%"
                    )
    price_difference_yoy.metric(
                    label = "Price difference (YoY)",
                    value = "$" + str(round(agg_data['close'].diff(periods = 252)[-1], 2)),
                    delta = str(round(agg_data['close'].pct_change(periods = 252)[-1]*100, 2)) + "%"
                    )

    week_high.metric(
                    label = "52 week high",
                    value = "$" + str(round(agg_data['high'].tail(252).max(), 2)),
                    )

    week_low.metric(
                    label = "52 week low",
                    value = "$" + str(round(agg_data['low'].tail(252).min(), 2)),
                    )

    st.plotly_chart(create_chart(agg_data), use_container_width=False)
    return None

display_webapp()
