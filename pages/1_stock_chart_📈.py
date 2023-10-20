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

      data = {'open_price': o,
              'high_price': h,
              'low_price': l,
              'closing_price': c,
              'volume': v,
              'vwap': vwap,
              'transactions': transactions,
              'date': ts}

      AggData = pd.DataFrame(data, index=[0])
      Aggs.append(AggData)

    AggData = pd.concat(Aggs)
    AggData = AggData.set_index("date")
    AggData['daily_return'] = AggData['closing_price'].pct_change()
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
        icon = data['results']['branding']['icon_url']

        return comp_name, market_cap, description, homepage_url, icon

    except:
        comp_name = data['results']['name']
        return comp_name

def get_sma_signals(agg_data, SMA1, SMA2):
    """
    Creates a dataframe that stores the SMA signals
    """

    signals = pd.DataFrame(index = agg_data.index)
    #signals['signal'] = 0

    signals['closing_price'] = agg_data['closing_price']
    signals['SMA1'] = agg_data['closing_price'].rolling(SMA1).mean()
    signals['SMA2'] = agg_data['closing_price'].rolling(SMA2).mean()

    #signals = clean_data(signals)
    #signals = melt_data(signals, "SMA1", "SMA2")

    return signals

def clean_data(data):
    """
    Drops all NaN values and resets the index of the DataFrame
    """
    clean_data = data.dropna()
    clean_data = clean_data.reset_index()
    return clean_data

def melt_data(data, var1, var2, variable_name, value_name):
    """
    Uses pd.melt to convert dataset into wide format
    """
    melt_data = pd.melt(data.reset_index(), id_vars= ['date'], value_vars=[var1, var2])
    melt_data = melt_data.rename(columns={'variable': variable_name, 'value': value_name})
    return melt_data

def generate_sma_trading_signals(data):
    """

    """

    buy_price = []
    sell_price = []
    sma_signal = []
    signal = 0

    for i in range(len(data)):
        if data['SMA1'][i] > data['SMA2'][i]:
            if signal != 1:
                buy_price.append(data['closing_price'][i])
                sell_price.append(np.nan)
                signal = 1
                sma_signal.append(signal)
            else:
                buy_price.append(np.nan)
                sell_price.append(np.nan)
                sma_signal.append(0)

        elif data['SMA1'][i] < data['SMA2'][i]:

            if signal != -1:
                buy_price.append(np.nan)
                sell_price.append(data['closing_price'][i])
                signal = -1
                sma_signal.append(signal)
            else:
                buy_price.append(np.nan)
                sell_price.append(np.nan)
                sma_signal.append(0)

        else:
            buy_price.append(np.nan)
            sell_price.append(np.nan)
            sma_signal.append(0)

    signal_list = []

    #Create DataFrames for signals - index is the date index
    buyprice = pd.DataFrame(buy_price, columns=['buy_price'], index = data.index)
    sellprice = pd.DataFrame(sell_price, columns=['sell_price'], index = data.index)
    position = pd.DataFrame(sma_signal, columns=['sma_signal'], index = data.index)

    signal_list.append(buyprice)
    signal_list.append(sellprice)

    trading_signals = pd.concat(signal_list)
    trading_signals = melt_data(trading_signals, "buy_price", "sell_price", "trading signal", "closing_price")
    trading_signals = trading_signals.dropna()
    return trading_signals, position

def get_return_data(agg_data, position, initial_capital):
    """
    """

    portfolio = pd.DataFrame(index = position.index).fillna(0.0)
    date_fp = position[position['sma_signal'] != 0].index[0]
    fp = agg_data['closing_price'].loc[date_fp]
    stock_bought = math.floor((initial_capital / fp))

    portfolio['sma_signal'] = position['sma_signal']
    portfolio['signal'] = position['sma_signal'].cumsum()
    portfolio['stock bought'] = stock_bought * portfolio['signal']
    portfolio['position'] = portfolio['stock bought'] * agg_data['closing_price']
    portfolio['cash'] = initial_capital - (portfolio['sma_signal'] * agg_data['closing_price'] * stock_bought).cumsum()
    portfolio['total'] = portfolio['position'] + portfolio['cash']
    portfolio['strategy_return'] = portfolio['total'].pct_change()
    portfolio['cum_strat_ret'] = ((1 + portfolio['strategy_return']).cumprod() -1)
    portfolio['bnh_cum_ret'] = ((1 + agg_data['daily_return']).cumprod() - 1)

    return portfolio

def create_agg_chart(agg_data, comp_name):
    """
    Uses Altair to display the final data
    """

    #Chart Title
    #chart_title = "Price of {co_name}".format(co_name = comp_name)

    #highlight effect on the chart
    highlight = alt.selection(type = 'single', on='mouseover', fields=['variable'], nearest=True)

    #Chart1 - Displays Agg Data
    agg_data = agg_data.reset_index()
    c = alt.Chart(agg_data).mark_line( color = "#6EAEC6").encode(
        x=alt.X('yearmonthdate(date):T', axis=alt.Axis(format="%Y %b", tickCount= alt.TimeIntervalStep("month", 1))),
        y='closing_price:Q'
    ).properties(
    width = 600,
    height = 300,
    )

    return c

def create_volume_chart(agg_data):
    """
    creates the volume chart using the aggdata
    """

    c = alt.Chart(agg_data.reset_index()).mark_bar( color = "#6EAEC6").encode(
    x=alt.X('yearmonthdate(date):T', axis=alt.Axis(format="%Y %b", tickCount= alt.TimeIntervalStep("month", 1))),
    y='volume:Q'
    ).properties(
    width = 600,
    height=100,
    )
    return c

def create_sma_chart(signal_data, trading_signals):
    """
    """

    #Chart 2 - Displays the SMA data
    c2 = alt.Chart(signal_data).mark_line(opacity= 0.6).encode(
        x=alt.X('yearmonthdate(date):T', axis=alt.Axis(format="%Y %b", tickCount= alt.TimeIntervalStep("month", 1))),
        y='closing_price:Q',
        color= alt.Color('SMA:N', scale=alt.Scale(
            domain=['SMA1', 'SMA2'],
            range=['#F29745', '#687169']
        )))

    #Chart 3.
    c3 = alt.Chart(trading_signals).mark_circle(size = 150).encode(
        x=alt.X('yearmonthdate(date):T', axis=alt.Axis(format="%Y %b", tickCount= alt.TimeIntervalStep("month", 1))),
        y='closing_price:Q',
        color= alt.Color('trading signal:N', scale=alt.Scale(
            domain=['buy_price', 'sell_price'],
            range =['#2F9421', '#C6866E']
        )))

    return alt.layer(c2, c3).resolve_scale(color='independent', opacity='independent')

def create_return_chart(return_data):
    """
    """
    c1 = alt.Chart(return_data.reset_index()).mark_line(color = "#6EAEC6").encode(
        x=alt.X('yearmonthdate(date):T', axis=alt.Axis(format="%Y %b", tickCount= alt.TimeIntervalStep("month", 1))),
        y=alt.Y('cum_strat_ret:Q', axis=alt.Axis(format=".0%")),
        ).properties(
        width = 600,
        height=100,
    )

    c2 = alt.Chart(return_data.reset_index()).mark_line(color = "#687169").encode(
        x=alt.X('yearmonthdate(date):T', axis=alt.Axis(format="%Y %b", tickCount= alt.TimeIntervalStep("month", 1))),
        y=alt.Y('bnh_cum_ret:Q', axis=alt.Axis(format=".0%")),
        ).properties(
        width = 600,
        height=100,
    )

    return c1+c2

def display_webapp():
    st.set_page_config(page_title="stock chart", page_icon="📈")

    with st.sidebar:
        #Ticker Options
        stock = st.text_input('Stock Ticker', 'AAPL')

        try:
            comp_name, market_cap, description, homepage_url, icon = get_ref_data(stock)
        except:
            comp_name = get_ref_data(stock)

        try:
            with st.expander("Company Description"):
                st.write(description)
        except:
            None

        st.divider()

        SMA1 = st.number_input("SMA1", value=40)
        st.divider()

        SMA2 = st.number_input("SMA2", value=252)
        st.divider()

    metric_container = st.container()
    button_container = st.container()
    chart_container = st.container()
    
    with button_container:
        start_date = (datetime.now() - relativedelta(years=+5)).strftime("%Y-%m-%d")
        end_date = datetime.now().strftime("%Y-%m-%d")
        oneMbt, sixMbt, oneYbt, fiveYbt, blank = st.columns([0.1, 0.1, 0.1, 0.1, 0.6], gap="small")

        if oneMbt.button('1M'):
            start_date = (datetime.now() - relativedelta(months=+1)).strftime("%Y-%m-%d")
        if sixMbt.button('6M'):
            start_date = (datetime.now() - relativedelta(months=+6)).strftime("%Y-%m-%d")
        if oneYbt.button('1Y'):
            start_date = (datetime.now() - relativedelta(years=+1)).strftime("%Y-%m-%d")
        if fiveYbt.button('5Y'):
            start_date = (datetime.now() - relativedelta(years=+5)).strftime("%Y-%m-%d")

    agg_data = get_aggregates(stock, start_date, end_date)

    with metric_container:
        st.header(stock + " - " + comp_name)
        price, price_change = st.columns(2)
        price.metric(label = "price", value = "$" + str(agg_data['closing_price'][-1]), delta = str(round(agg_data['daily_return'][-1] * 100, 2)) + "%")
        price_change.metric(value = agg_data['closing_price'].diff()[-1])
    
    #Strategy 1 - Simple Moving Average Strategy
    #A. Get sma_data signals
    sma_signals = get_sma_signals(agg_data, SMA1, SMA2)
    sma_signals_wide = melt_data(sma_signals, "SMA1", "SMA2", "SMA", "closing_price")

    #B. Generates Trading signals for the SMA strategy
    trading_signals, position = generate_sma_trading_signals(sma_signals)

    #C. Get return data
    return_data = get_return_data(agg_data, position, 100000) #initial_capital is fixed at $100000

    #3. Display Chart

    
    with chart_container:
        agg_chart = create_agg_chart(agg_data, comp_name)
        volume_chart = create_volume_chart(agg_data)
        return_chart = create_return_chart(return_data)

        sma_chart = create_sma_chart(sma_signals_wide, trading_signals)
        combined_chart = agg_chart + sma_chart
        final_chart = alt.vconcat(combined_chart, volume_chart, return_chart)
        st.altair_chart(final_chart, use_container_width=True)

        st.write("Buy/Sell Signals")
        st.dataframe(trading_signals, use_container_width=True)

    return None

display_webapp()
