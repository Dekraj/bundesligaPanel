from zoneinfo import ZoneInfo
from datetime import datetime, time, timezone, timedelta
from io import BytesIO
import requests
from PIL import Image, ImageDraw, ImageFont
from classes.Broker import BrokerClient
import asyncio
import threading
from threading import Timer
import json
from utils.utility_functions import getNextMatch, clearBoard, make_text_img, generate_overtime, getMatchOfGameday, load_team_logo
from configs import config


class Scoreboard:
    def __init__(self):
        self.nextMatch = getNextMatch()
        self.next_game_time = datetime.fromisoformat(self.nextMatch["matchDateTime"]).replace(tzinfo=ZoneInfo("Europe/Berlin"))
        self.game_day = self.nextMatch["group"]["groupOrderID"]
        self.next_home_team_url = self.nextMatch["team1"]["teamIconUrl"]
        self.next_away_team_url = self.nextMatch["team2"]["teamIconUrl"]
        self.time_now_de = datetime.now(ZoneInfo("Europe/Berlin"))

        self.gametime_img = None
        self.gamedate_img = None
        self.score_img = None
        self.current_time_img = None

        self.home_team_logo = None
        self.away_team_logo = None

        self.state = "inital"
        self.data_loaded = False
        self.broker = None
        self.fetch_team_logos()
    
        if(self.next_game_time > self.time_now_de):
            self.game_finished = False
            self.show_wait_next_game()
        elif(self.nextMatch["matchIsFinished"] == False):
            self.game_finished = False
            self.show_game_live()
        else:
            self.game_finished = True
            self.show_game_over()

    def show_game_live(self):
        self.state = "game_live"
        self.data_loaded = False
        clearBoard()
        #Live spiel anzeigen
        self.broker = BrokerClient("openligadb/bl1/2025/" + self.game_day, self.on_broker_message)
        # self.broker = BrokerClient("openligadb/25testmqtt/2025/"+ str(self.game_day), self.on_broker_message)
        home_goals =(self.nextMatch.get("matchResults", [{}])[1].get("pointsTeam1", 0)
                     if len(self.nextMatch.get("matchResults", [])) > 1
                     else 0)
        away_goals =(self.nextMatch.get("matchResults", [{}])[1].get("pointsTeam2", 0)
                     if len(self.nextMatch.get("matchResults", [])) > 1
                     else 0)

        self.update_score(home_goals,away_goals)
        self.broker.start()
        self.update_time(1)
        threading.Thread(target=self.start_async_timer).start()
        self.data_loaded = True
    
    def on_broker_message(self, client, userdata, msg):
        message = msg.payload.decode()
        data = json.loads(message)
        if data["Team1"]["TeamId"] != config.my_team_id and data["Team2"]["TeamId"] != config.my_team_id:
            return
        filtered = [data]
        home_goals = filtered[0]["MatchResults"][1]["PointsTeam1"]
        away_goals = filtered[0]["MatchResults"][1]["PointsTeam2"]
        self.update_score(home_goals, away_goals)
        self.game_finished = filtered[0]["MatchIsFinished"]

    def stop_broker(self):
        if self.broker:
            self.broker.stop()

    def update_score(self, home_goals, away_goals):
        score = str(home_goals) + " - " + str(away_goals) 
        self.score_img = make_text_img(score, config.font_small, config.font_white)

    def start_async_timer(self):
        asyncio.run(self.start_timer())

    async def start_timer(self):
        minutes_since_start = int((self.time_now_de - self.next_game_time).total_seconds() // 60 + 1)
        guessed_overtime = generate_overtime()

        for i in range(minutes_since_start, 45 + guessed_overtime + 15 + 45):
            if(i< 45):
                self.update_time(str(i+1) +"'")
            if(45 <= i < 45 + guessed_overtime):
                self.update_time("45+" + str(i - 45 + 1)+"'")
            if(45 + guessed_overtime <= i < 45 + guessed_overtime + 15):
                self.update_time("Pause")
            if(45 + guessed_overtime + 15 <= i <= 46 + guessed_overtime + 15 + 45):
                clearBoard()
                self.update_time(str(i - guessed_overtime - 15 + 1)+"'")   
            await asyncio.sleep(60) 

        overtime = 1
        while(self.game_finished == False):
            self.update_time("90+" + str(overtime)+ "'")
            overtime += 1
            await asyncio.sleep(60)
        self.game_ended()
    def game_ended(self):
        self.stop_broker()
        self.show_game_over()

    def update_time(self, current_minute):
        self.current_time_img = make_text_img(str(current_minute), config.font_medium, config.font_white)

    def show_game_over(self):
        self.state="game_over"
        self.data_loaded = False
        clearBoard()
        end_game_data = getMatchOfGameday(self.game_day)
        self.current_time_img = make_text_img("Ende", config.font_medium, config.font_white)
        
        home_goals = end_game_data[0]["matchResults"][1]["pointsTeam1"]
        away_goals = end_game_data[0]["matchResults"][1]["pointsTeam2"]
        score = str(home_goals) + " - " + str(away_goals)

        self.score_img = make_text_img(score, config.font_medium, config.font_white)
        self.data_loaded = True

        days_until_monday = (0 - self.time_now_de.weekday()) % 7
        if days_until_monday == 0 and self.time_now_de.hour >= 9:
            days_until_monday = 7 
        next_monday = (self.time_now_de + timedelta(days=days_until_monday)).replace(hour=9, minute=0, second=0, microsecond=0)
        delay_to_new_week = (next_monday - self.time_now_de).total_seconds()
        Timer(delay_to_new_week, self.show_wait_next_game).start()

    def show_wait_next_game(self):
        if(self.state != "inital"):
            self.nextMatch = getNextMatch()
        self.state ="wait_next_game"
        self.data_loaded = False
        clearBoard()
        # Fetch data of next game
        match_gametime = self.next_game_time.strftime("%H:%M")
        self.gametime_img = make_text_img(match_gametime, config.font_medium, config.font_white, [0,0,1,0])

        # If the game is not this week then show the date instead of a weekday
        when_is_game = None
        if(self.time_now_de + timedelta(days=7) >= self.next_game_time):
            when_is_game = config.wochentage[self.next_game_time.weekday()]
        else:
            when_is_game = self.next_game_time.strftime("%d.%m.%y")

        self.gamedate_img = make_text_img(when_is_game, config.font_small, config.font_white, [0,0,3,0])
        
        self.data_loaded = True

        delay_to_gamestart = (self.next_game_time - self.time_now_de).total_seconds()
        if delay_to_gamestart < 0:
            delay_to_gamestart = 0
        Timer(delay_to_gamestart, self.show_game_live).start()

    def fetch_team_logos(self):
          # get home team logo from url
        # home_team_response = requests.get(self.next_home_team_url, headers=config.headers)
        home_team_logo_not_scaled = load_team_logo(self.next_home_team_url)
        # resize logo so that it fits the LEDboard perfectly
        original_width_home, original_height_home = home_team_logo_not_scaled.size
        new_width_home = int( original_width_home * ( config.total_height_LEDboard / original_height_home))
        home_team_logo_scaled = home_team_logo_not_scaled.resize((new_width_home, config.total_height_LEDboard), Image.LANCZOS)
        self.home_team_logo = home_team_logo_scaled.crop((new_width_home - config.max_pixel_width_logos,0,new_width_home, config.total_height_LEDboard))

        # get away team logo from url
        away_team_logo_not_scaled = load_team_logo(self.next_away_team_url)
        # resize logo so that it fits the LEDboard perfectly
        original_width_away, original_height_away = away_team_logo_not_scaled.size
        new_width_away = int(original_width_away * (config.total_height_LEDboard / original_height_away))
        away_team_logo_scaled = away_team_logo_not_scaled.resize((new_width_away, config.total_height_LEDboard), Image.LANCZOS)
        self.away_team_logo = away_team_logo_scaled.crop((0,0, new_width_away, config.total_height_LEDboard))
