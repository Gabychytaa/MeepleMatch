import pandas as pd
import requests
import scipy.spatial.distance as dist
from bs4 import BeautifulSoup
import streamlit as st

def scrape_user(username:str):
    """
    Scrapes BoardGameGeek (BGG) to retrieve all board games rated by a specific user.

    :param username: BGG username to scrape ratings for.
    :type username: `str`

    :return: A DataFrame containing the user's rated games, with columns: 'BGGId', 'Rating', and 'Username'.
    :rtype: `pd.DataFrame`
    """  
    url = f'https://boardgamegeek.com/collection/user/{username}?rated=1&subtype=boardgame&ff=1'
    soup = BeautifulSoup(requests.get(url).content, features="html.parser")
    grid_games = soup.find_all('a', attrs={'class':'primary'})
    game_ids = [int(game['href'].split('/')[2]) for game in grid_games]
    game_names = [game.get_text() for game in grid_games]

    grid_ratings = soup.find_all('div', attrs={'class':'ratingtext'})
    game_ratings = [float(rating.get_text()) for rating in grid_ratings]

    user_df = pd.DataFrame({
        'BGGId' : game_ids,
        'Rating' : game_ratings,
        'Username' : username
    })

    st_display_df = pd.DataFrame({
        'Name' : game_names,
        'Rating' : game_ratings
    })
    return user_df, st_display_df

@st.cache_data
def read_data():
    """
    Reads data stored locally.\n
    
    :return: games, ratings.
    :rtype: `pd.DataFrame`

    """ 
    games = pd.read_csv('data/games.csv')
    games.set_index('BGGId',inplace=True)
    ratings = pd.read_csv('data/user_ratings.csv')
    return games, ratings

def intersect(df1:pd.DataFrame, df2:pd.DataFrame, column:str):
    """
    Returns the subset of rows from `df1` where the values in the specified column also appear in `df2`.

    :param df1: The first DataFrame (typically the larger one) to be filtered.
    :type df1: `pd.DataFrame`
    :param df2: The second DataFrame used to determine the `int`ersection.
    :type df2: `pd.DataFrame`
    :param column: The name of the column on which to perform the `int`ersection.
    :type column: `str`

    :return: A DataFrame containing rows from `df1` where `column` values exist in `df2[column]`.
    :rtype: `pd.DataFrame`
    """  
    intersection = df1[df1[column].isin(df2[column])]
    return intersection

def filter_nan_columns(df:pd.DataFrame, no_nan:int = 5):
    """
    Drops columns from a DataFrame that contain fewer than a specified number of non-NaN values.

    :param df: The DataFrame to be filtered.
    :type df: `pd.DataFrame`
    :param no_nan: Minimum number of non-NaN values required for a column to be retained.
    :type no_nan: `int`

    :return: A filtered DataFrame containing only the columns with at least `metric` non-NaN values.
             If more than 10,000 columns meet this criterion, only the top 10,000 columns with the most non-NaN values are retained.
    :rtype: `pd.DataFrame`
    """
    metrics = len(df.index) - df.isna().sum()
    good_columns = [column for column, index in metrics.items() if index >= no_nan]

    # If good_columns is still too many, filter for only the top 10k
    if len(good_columns) > 10000:
        best_columns = metrics.sort_values(ascending=False)[0:10000]
        filtered_df = df[best_columns.index]
        return filtered_df
    else:
        filtered_df = df[good_columns]
        return filtered_df
    
def similarity(df:pd.DataFrame, column:str, metric:str = "euclidean"):
    """
    Computes the similarity between the given column and all others in the DataFrame,
    using a specified distance metric.

    Similarity is calculated as the inverse of the pairwise distance:  
    `similarity = 1 / (1 + distance)`, where distance is computed using SciPy's `pdist`.

    :param df: DataFrame containing the data to compute similarities on
    :type df: `pd.DataFrame`

    :param metric: Distance metric to use for the similarity calculation. Supported metrics include:
        'braycurtis', 'canberra', 'chebyshev', 'cityblock', 'correlation', 'cosine', 'dice',
        'euclidean', 'hamming', 'jaccard', 'jensenshannon', 'kulczynski1', 'mahalanobis',
        'matching', 'minkowski', 'rogerstanimoto', 'russellrao', 'seuclidean',
        'sokalmichener', 'sokalsneath', 'sqeuclidean', 'yule'.
    :type metric: `str`

    :param column: The label of the column to calculate similarities for.
    :type column: `str`

    :return: A Series of similarity scores between the specified column and all others, sorted in descending order.
    :rtype: `pd.Series`
    """
    # Calculate distances and store them in a df
    distances = pd.DataFrame(1/(1 + dist.squareform(dist.pdist(df, metric = metric))),
                              index = df.index, 
                              columns = df.index)
    # Get the last column (user) distances, i.e. similarity to other columns (other users) and sort them in descending order
    similarity = distances.loc[column].sort_values(ascending=False)
    return similarity
