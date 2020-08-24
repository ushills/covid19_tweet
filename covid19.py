import argparse
import configparser
import requests
from datetime import datetime

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import tweepy
from uk_covid19 import Cov19API

# set configuation file path
parser = argparse.ArgumentParser(description="Tweet latest COVID-19 data for England")
parser.add_argument(
    "--config",
    "-c",
    metavar="path",
    type=str,
    help="configuation file path",
    required=True,
    dest="config_file_path",
)
args = parser.parse_args()
config_full_path = args.config_file_path

# import configuration
config = configparser.ConfigParser()
config.read(config_full_path)
twitter_oath_key = config["twitter"]["oath_key"]
twitter_oath_secret = config["twitter"]["oath_secret"]
twitter_access_key = config["twitter"]["access_key"]
twitter_access_secret = config["twitter"]["access_secret"]
graph_file = config['files']['graph_file']
last_modified_file = config['files']['last_modified_file']

area = ["areaType=nation", "areaName=England"]

structure = {"date": "date", "newCasesByPublishDate": "newCasesByPublishDate"}


def get_covid_data():
    api = Cov19API(filters=area, structure=structure)
    data = api.get_json()
    return data


def get_last_modified():
    latest_update_header_response = requests.get(
        "https://api.coronavirus.data.gov.uk/v1/data?filters=areaType=nation;areaName=england&structure=%7B%22name%22:%22areaName%22%7D"
    )
    latest_update_header = latest_update_header_response.headers["Last-Modified"]
    last_modified_datetime = datetime.strptime(
        latest_update_header, "%a, %d %b %Y %H:%M:%S %Z"
    )
    return last_modified_datetime


def get_local_last_modified():
    try:
        with open(last_modified_file) as f:
            local_last_modified = f.read()
            # 2020-08-23 14:05:29
            return datetime.strptime(local_last_modified, '%Y-%m-%d %H:%M:%S')
    except:
        return datetime(1970, 1, 1, 0, 0, 0)


def write_last_modified_to_file(last_modified):
    try:
        with open(last_modified_file, "w") as f:
            f.write(str(last_modified))
    except:
        raise


def check_last_modified():
    last_modified_from_site = get_last_modified()
    local_last_modified = get_local_last_modified()
    if last_modified_from_site > local_last_modified:
        write_last_modified_to_file(last_modified_from_site)
        return True
    else:
        write_last_modified_to_file(local_last_modified)
        return False


def check_data_is_current(data):
    latest_date_str = data["data"][0]["date"]
    latest_date = datetime.strptime(latest_date_str, "%Y-%m-%d")
    todays_date = datetime.now()
    return latest_date.date() == todays_date.date()


def add_7_day_average(data):
    data = pd.json_normalize(data["data"])
    data = data.sort_values(by=["date"], ascending=True)
    data.reset_index(drop=True, inplace=True)
    data["7DayAverage"] = data.iloc[:, 1].rolling(window=7).mean()
    latest_data = data.iloc[-1, :]
    latest_7day_average = latest_data["7DayAverage"].astype(int)
    return data, str(latest_7day_average)


def create_graph(data, latest_7day_average):
    ax = plt.gca()
    x_values = [datetime.strptime(d, "%Y-%m-%d").date() for d in data["date"]]
    formatter = mdates.DateFormatter("%b-%y")
    ax.xaxis.set_major_formatter(formatter)
    plt.xticks(rotation=45)
    plt.tick_params('x', labelsize='small')
    plt.box(on=None)
    plt.plot(x_values, data["7DayAverage"], label="7 Day Average")
    plt.title("COVID-19 7-Day Average England - " + latest_7day_average)
    plt.savefig(graph_file)


def create_tweet(latest_7day_average):
    # Authenticate to Twitter
    auth = tweepy.OAuthHandler(twitter_oath_key, twitter_oath_secret)
    auth.set_access_token(twitter_access_key, twitter_access_secret)

    api = tweepy.API(auth)

    try:
        api.verify_credentials()
        print("Authentication OK")
    except:
        print("Error during authentication")

    # send tweet
    media = api.media_upload(graph_file)
    media_id = media.media_id_string
    media_id
    tweet_text = (
        "Latest 7-day average for COVID-19 in England - "
        + latest_7day_average
        + " #COVID19 #python #pandas"
    )
    api.update_status(tweet_text, media_ids=[media.media_id])


if __name__ == "__main__":
    raw_data = get_covid_data()
    if check_last_modified():
        data, latest_7day_average = add_7_day_average(raw_data)
        create_graph(data, latest_7day_average)
        create_tweet(latest_7day_average)
        print("Data updated")
    else:
        print("Data has not been updated")
