import streamlit as st
import pandas as pd
from functions import functions
import plotly.express as px

def main():

    # Load data
    games, ratings = functions.read_data()
    
    # Title
    st.title('MeepleMatch')
    st.markdown("### Boardgame recommender powered by [BGG](https://boardgamegeek.com)")

    # Get user input
    with st.form(key='user_form'):
        col1, col2 = st.columns(2)
        with col1:
            user = st.text_input(label = 'BGG username',
                                 help = "Your username on BoardGameGeek")
        with col2:
            n_recs = st.slider(label = 'Recommend games', 
                               min_value=0,
                               max_value=30,
                               value=15,
                               step=1)
        submit = st.form_submit_button('Get Recommendations')
    with st.expander(label = "Advanced options"):
        col1, col2 = st.columns(2)
        with col1:
            obscure_filter = st.checkbox(label = "Show me niche games",
                                        value = False,
                                        help = "Include lesser-known games (with fewer ratings) in the recommendations.")
        with col2:
            weight_filter = st.radio(label = "Weight of games",
                                     options = range(1, 6),
                                     horizontal = True,
                                     index = 4,
                                     help = "Filters games based on BGG community weight rating (complexity). You'll see games with a maximum weight of the selected level: Light (1), Medium Light (2), Medium (3), Medium Heavy (4), Heavy (5)")

    st.markdown("Created by [arnaurr94](https://github.com/arnaurr94)") # App developer

    # Start running the code after user input
    if submit:

        # Include a loading gif for increased user experience
        loading_placeholder = st.empty()
        with loading_placeholder:
            st.markdown("""<div style='text-align: center;'>
                            <img src="http://icon-library.com/images/cat-icon-gif/cat-icon-gif-1.jpg" width="300">
                            <p style='font-size:16px;'>Searching games and ratings...</p>
                            </div>""",
                            unsafe_allow_html=True)
            
        try:   # Error handling for user input
            user_df, st_display_df = functions.scrape_user(user)
            if user_df.empty:
                loading_placeholder.empty()   # Closes the loading gif
                st.error("Could not fetch enough rated games for this username. Please make sure the BGG profile exists and has at least 5 rated games.")
                st.stop()
        except:
            loading_placeholder.empty()   # Closes the loading gif
            st.error("An error occurred while fetching your data. Please try again later.")
            st.stop()

        loading_placeholder.empty()   # Closes the loading gif

        # Display user game ratings
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Games rated", len(st_display_df))
        with col2:
            st.metric("Average rating", round(st_display_df['Rating'].mean(), 1))

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("###### Board game ratings")   
            st.dataframe(st_display_df, hide_index = True)
        with col2:
            st.markdown(f"###### Distribution of {user}'s ratings")
            fig = px.bar(st_display_df.groupby('Rating').count(),
                        color_discrete_sequence = ['#FF6F61'])
            fig.update_layout(yaxis_title = None,
                            xaxis = dict(dtick=1),
                            showlegend = False)
            st.plotly_chart(fig)

        # Include a loading gif for increased user experience
        loading_placeholder = st.empty()
        with loading_placeholder:
            st.markdown("""<div style='text-align: center;'>
                            <img src="http://icon-library.com/images/cat-icon-gif/cat-icon-gif-1.jpg" width="300">
                            <p style='font-size:16px;'>Working on your recommendations...</p>
                            </div>""",
                            unsafe_allow_html=True)
            
        # Finds the games shared by the user and the database.
        common_games = functions.intersect(ratings, user_df, column='BGGId')

        # Pivots the dataframe to generate a matrix with users as columns, games as rows and ratings as values.
        pivot_ratings = common_games.pivot_table(index='BGGId', columns='Username', values='Rating')

        # Many users have only a few games in common with our target user. Limit the comparison to users that are similar to our target, i.e. at least 5 items in common
        filtered_pivot = functions.filter_nan_columns(df = pivot_ratings, no_nan = 5)

        # Add target user to the df
        if user in filtered_pivot.columns:   # Prevents duplicate user if already in database
            merged_user = filtered_pivot
        else:
            pivot_user = user_df[user_df['BGGId'].isin(pivot_ratings.index)].pivot_table(index='BGGId', columns='Username', values='Rating')
            merged_user = pd.merge(left = filtered_pivot, right = pivot_user, on = 'BGGId')

        # Fill NaN values with average rating of the game.
        # For some reason .fillna() only works with the transposed df.
        no_nans = merged_user.transpose().fillna(games['AvgRating'])

        # Calculate similarity for user
        similarity = functions.similarity(df = no_nans, column = user, metric= 'cosine')

        # Get games target user has not rated, only for the top 50 users in similarity
        ratings_count = ratings.groupby('BGGId').count()
        if obscure_filter == True:   # activated upon user input. Gets all games, regardless of total number of ratings
            not_played_games = ratings[(ratings['Username'].isin(similarity.index[1:51])) & ~(ratings['BGGId'].isin(user_df.BGGId))].pivot_table(index='BGGId', columns='Username', values='Rating')
        else:   # Gets games with >= 2k number of ratings
            wellknown_games = [game_id for game_id, count in ratings_count['Rating'].items() if count >= 2000]
            not_played_games = ratings[(ratings['Username'].isin(similarity.index[1:51])) & (ratings['BGGId'].isin(wellknown_games)) & ~(ratings['BGGId'].isin(user_df.BGGId))].pivot_table(index='BGGId', columns='Username', values='Rating')   

        # Fill NaN values with average rating of the game. Undo the transpose
        npg_no_nans = not_played_games.transpose().fillna(games['AvgRating']).transpose()

        # Get recommendations for user
        rec_user = npg_no_nans.copy()

        # Activated upon user input. Gets games with weight(difficulty) <= then user input.
        weighted_games = [id for id in rec_user.index if games.loc[id, 'GameWeight'] <= weight_filter]
        rec_user = rec_user[rec_user.index.isin(weighted_games)]

        for name in rec_user.columns:
            rec_user[name] = rec_user[name] * similarity[name]

        rec_user['Total'] = rec_user.apply(sum,axis=1)
        sorted_rec = rec_user.sort_values('Total', ascending=False)

        loading_placeholder.empty()   # Closes the loading gif

        # Print recommendations
        st.write(f'### MeepleMatch top {n_recs} recommendations for {user}\n')

        # Define number of columns per row
        num_cols = 3

        # Loop over recommended games
        for column_id, id in enumerate(sorted_rec.head(int(n_recs)).index):
            # Create a new row every `num_cols` items
            if column_id % num_cols == 0:
                cols = st.columns(num_cols)

            game_url = f"https://boardgamegeek.com/boardgame/{id}"
            image_url = games.loc[id]['ImagePath']
            game_name = games.loc[id]['Name']
        
            # Select column for current card in current row
            with cols[column_id % num_cols]:
                st.markdown(
                    f"""
                    <a href="{game_url}" target="_blank" style="text-decoration: none;">
                        <img src="{image_url}" alt="{game_name}"
                        style="width: 300px; height: 300px; object-fit: cover; border-radius: 8px;" />
                        <div style="text-align: center; margin-top: 8px; font-weight: bold;">{game_name}</div>
                    </a>
                    """,
                    unsafe_allow_html=True
                )

        # Plot a histogram of how many games other users have in common with the current user.
        with st.expander(label="Show me the data"):
            col1, col2 = st.columns(2)
            with col1:
                st.metric(label = "Users compared", value = pivot_ratings.shape[1])
                st.caption("Number of users you were compared to.")
            with col2:
                percentage = round((pivot_ratings.shape[1] / ratings['Username'].nunique()) * 100)
                st.metric(label = "Percentage of User Base Compared", value = f"{percentage}%")
                st.caption("Proportion of the entire BGG community compared against your profile.")

            most_rated_games = common_games.groupby('BGGId').count().sort_values(by='Rating', ascending = False).head(5)
                
            fig = px.bar(data_frame = most_rated_games, 
                            x = [games.loc[id, 'Name'] for id in most_rated_games.index],
                            y = most_rated_games['Rating'],
                            title=f"Top 5 Games you rated with the most community ratings",
                            color_discrete_sequence=['#FF6F61'])
            fig.update_layout(yaxis_title = 'ratings count',showlegend=False, bargap=0.1)
            st.plotly_chart(fig, use_container_width=True)
        
            fig = px.histogram(pivot_ratings.notna().sum(axis=0), nbins=len(pivot_ratings.index),
                                title=f"Distribution of number of games you share with other users",
                                labels={'value': 'Games in common'},
                                color_discrete_sequence=['#FF6F61'])
            fig.update_layout(yaxis_title = 'user count',showlegend=False, bargap=0.1)
            st.plotly_chart(fig, use_container_width=True)

if __name__ == '__main__':
    main()