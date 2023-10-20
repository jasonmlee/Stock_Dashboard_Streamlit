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

key = "G5O2ZIhaZExN4D04fphejimYOduuPfoK"
POLYGON_TICKER_DETAILS_V3 = 'https://api.polygon.io/v3/reference/tickers/{}?apiKey={}'
POLYGON_TICKER_NEWS = 'https://api.polygon.io/v2/reference/news?ticker={}&limit=100&apiKey={}'

def get_news(stock):
    """
    """

    key = "0a9cfccc02264d8aabb3d83a58cc38df"
    category ="business"
    fr_date = (datetime.now() - relativedelta(months=+1)).strftime("%Y-%m-%d")
    to_date = datetime.now().strftime("%Y-%m-%d")
    NEWS_API = 'https://newsapi.org/v2/everything?q={}&language=en&from={}&to={}&sortBy=publishedAt&apiKey={}'

    session = requests.Session()
    r = session.get(NEWS_API.format(stock, fr_date, to_date, key))
    news_data = r.json()

    articles = news_data['articles']

    news_list = []

    for i in range(len(articles)):
        source = articles[i]['source']['name']
        title = articles[i]['title']
        description = articles[i]['description']
        url = articles[i]['url']
        image = articles[i]['urlToImage']
        date_published = articles[i]['publishedAt']
        content = articles[i]['content']

        dict1 = {'source': source,
                'title': title,
                'description': description,
                'url': url,
                'image': image,
                'date_published': date_published,
                'content': content}

        news = pd.DataFrame(dict1, index=[0])
        news_list.append(news)

    news_df = pd.concat(news_list)
    news_df = news_df.reset_index()

    return news_df

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

def display_webapp():
    st.set_page_config(page_title="news", page_icon="📈")

    with st.sidebar:
        #Ticker Options
        stock = st.text_input('Stock Ticker', 'AAPL')

        try:
            comp_name, market_cap, description, homepage_url, icon = get_ref_data(stock)
        except:
            comp_name = get_ref_data(stock)

        st.header(comp_name)

        dashboard_select = st.selectbox("which dashboard?", ('Chart', 'News'))

        try:
            with st.expander("Company Description"):
                st.write(description)
        except:
            None

        st.markdown("***")

        news_data = get_news(stock)
        st.header("Latest News")

        for i in range(len(news_data)):
            col1, col2, col3 = st.columns(3)
            with st.container():
                url = news_data['url'][i]
                date = news_data['date_published'][i]
                source = news_data['source'][i]
                title = news_data['title'][i]
                image = news_data['image'][i]

                col1.write(source)
                col2.write(title + " [link](%s)" % url)
                col3.image(image)
                st.divider()

    else:
        return None
    return None

display_webapp()
