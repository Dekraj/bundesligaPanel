import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from io import BytesIO
from threading import Timer
import paho.mqtt.client as mqtt
import adafruit_blinka_raspberry_pi5_piomatter as piomatter
import random

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

# 16 = VfB Stuttgart
my_team_id = 16

# 128px for 2x1 matrices. Change to 64 if you're using a single matrix.
total_width_LEDboard = 64
total_height_LEDboard = 32

# Arrangement of Logos and Text:
# <Logo of home team (30%)> <game text (40%)> <Logo of enemy team (30%)>
# determines how many percent of the Logo should be visible 
# (If you have a wider screen you can show more of the team logos)
logo_visible_amount = 0.3
max_pixel_width_logos = int(total_width_LEDboard * 0.3)

font_medium = ImageFont.truetype("arial.ttf", 12)
font_small = ImageFont.truetype("arial.ttf", 10)
font_white = (255,255,255)

wochentage = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]


# LED Board init
canvas = Image.new("RGB", (total_width_LEDboard, total_height_LEDboard), (0,0,0))
geometry = piomatter.Geometry(width=total_width_LEDboard, height=total_height_LEDboard,
                              n_addr_lines=4, rotation=piomatter.Orientation.Normal)
framebuffer = np.asarray(canvas) + 0
matrix = piomatter.PioMatter(colorspace=piomatter.Colorspace.RGB888Packed,
                             pinout=piomatter.Pinout.AdafruitMatrixBonnet,
                             framebuffer=framebuffer,
                             geometry=geometry)

def clearBoard():
    global canvas, framebuffer, matrix
    canvas.paste((0,0,0), [0,0,canvas.width, canvas.height])
    framebuffer[:] = np.asarray(canvas)                         

def getNextMatch():
    data = requests.get("https://api.openligadb.de/getmatchdata/bl1/2025/").json();
    filtered = [row for row in data if row["team1"]["teamId"] == my_team_id or row["team2"]["teamId"] == my_team_id]
    now = datetime.now(timezone.utc)
    days_since_monday = now.weekday()
    monday_this_week = now - timedelta(days=days_since_monday)
    monday_at_9 = monday_this_week.replace(hour=9, minute=0, second=0, microsecond=0)
    monday_iso = monday_at_9.strftime("%Y-%m-%dT%H:%M:%SZ")    
    #return first gamedate found after this weeks monday
    for row in filtered:
        if row["matchDateTimeUTC"] > monday_iso:
            return row

def getMatchOfGameday(gameday):
    data = requests.get('https://api.openligadb.de/getmatchdata/bl1/2025/'+ str(gameday)).json();
    filtered = [row for row in data if row["team1"]["teamId"] == my_team_id or row["team2"]["teamId"] == my_team_id]
    return filtered

def make_text_img(text, font, font_color):
    x,y,width,height = font.getbbox(text) 
    text_img = Image.new("RGB", (int(width), int(height)),(0,0,0)) 
    draw = ImageDraw.Draw(text_img) 
    draw.text((0,0),text, font=font, fill=font_color) 
    return text_img

def generate_overtime():
    # Currently its not possible to fetch the overtime via the API
    # so we guess the overtime
    over_time_minutes = [1,2,3,4,5,6,7] 
    weights = [0.03, 0.22, 0.25, 0.22, 0.17, 0.1, 0.01]
    over_time = random.choices(over_time_minutes, weights=weights, k=1)[0]
    return over_time 


class BrokerClient:
    def __init__(self, topic, on_message_callback):
        self.client = mqtt.Client()
        self.client.tls_set()
        self.client.on_connect = self.on_connect
        self.client.on_message = on_message_callback
        self.topic = topic
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            client.subscribe(self.topic)
        else:
            print("Connecting error to the broker", rc)
    def start(self):
        self.client.connect("broker.hivemq.com", port=8883)
        self.client.loop_start()
    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()


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

        #Fetch home team fetch away team fetch next game time



    def show_game_live(self):
        self.state = "game_live"
        self.data_loaded = False
        clearBoard()
        #Live spiel anzeigen
        self.broker = BrokerClient("openligadb/bl1/2025/" + self.game_day, self.on_broker_message)
        self.broker.start()
        self.start_timer()
        self.data_loaded = True


    def on_broker_message(self, client, userdata, msg):
        print("Neue Daten:", msg.topic, msg.payload.decode())


    def stop_game(self):
        if self.broker:
            self.broker.stop()

    def update_score(self):
        score = str(self.home_goals) + " - " + str(self.away_goals) 
        self.score_img = make_text_img(score, font_small, font_white)


    def start_timer(self):
        minutes_since_start = int((self.time_now_de - self.next_game_time).total_seconds() // 60 + 1)
        guessed_overtime = generate_overtime()

        for i in range(minutes_since_start, 45 + guessed_overtime + 15 + 45):
            if(i< 46):
                self.update_time(str(i+1))
            if(46 <= i < 46 + guessed_overtime):
                self.update_time("45 + " + str(i - 45))
            if(46 + guessed_overtime <= i < 46 + guessed_overtime + 15):
                self.update_time("Pause")
            if(46 + guessed_overtime + 15 <= i <= 46 + guessed_overtime + 15 + 45):
                self.update_time(str(i - guessed_overtime - 15))
            time.sleep(60)

        overtime = 1
        while(self.game_finished == False):
            self.update_time("90 + " + str(overtime))
            overtime += 1
            time.sleep(60)

    def update_time(self, current_minute):
        self.current_time_img = make_text_img(str(current_minute), font_medium, font_white)

    def show_game_over(self):
        self.state="game_over"
        self.data_loaded = False
        clearBoard()
        end_game_data = getMatchOfGameday(self.game_day)

        home_goals = end_game_data[0]["matchResults"][1]["pointsTeam1"]
        away_goals = end_game_data[0]["matchResults"][1]["pointsTeam2"]
        score = str(home_goals) + " - " + str(away_goals)

        self.score_img = make_text_img(score, font_medium, font_white)
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
        # If the game is not this week then show the date instead of a weekday
        if(self.time_now_de + timedelta(days=7) >= self.next_game_time):
            match_gamedate = wochentage[date_object.weekday()]
        else:
            match_gamedate = date_object.strftime("%d.%m.%y")

        self.gametime_img = make_text_img(match_gametime, font_medium, font_white)
        self.gamedate_img = make_text_img(match_gamedate, font_small, font_white)
        self.data_loaded = True

        delay_to_gamestart = (self.next_game_time - self.time_now_de).total_seconds()
        if delay < 0:
            delay = 0
        Timer(delay, self.show_game_life).start()

    def fetch_team_logos(self):
          # get home team logo from url
        home_team_response = requests.get(self.next_home_team_url, headers=headers)
        home_team_logo_not_scaled = Image.open(BytesIO(home_team_response.content))
        # resize logo so that it fits the LEDboard perfectly
        original_width_home, original_height_home = home_team_logo_not_scaled.size
        new_width_home = int( original_width_home * ( total_height_LEDboard / original_height_home))
        home_team_logo_scaled = home_team_logo_not_scaled.resize((new_width_home, total_height_LEDboard), Image.LANCZOS)
        self.home_team_logo = home_team_logo_scaled.crop((new_width_home - max_pixel_width_logos,0,new_width_home, total_height_LEDboard))

        # get away team logo from url
        away_team_response = requests.get(self.next_away_team_url, headers=headers)
    
        away_team_logo_not_scaled = Image.open(BytesIO(away_team_response.content))
        # resize logo so that it fits the LEDboard perfectly
        original_width_away, original_height_away = away_team_logo_not_scaled.size
        new_width_away = int(original_width_away * ( total_height_LEDboard / original_height_away))
        away_team_logo_scaled = away_team_logo_not_scaled.resize((new_width_away, total_height_LEDboard), Image.LANCZOS)
        self.away_team_logo = away_team_logo_scaled.crop((0,0, new_width_away, total_height_LEDboard))


scoreboard = Scoreboard()

while True:

    if(scoreboard.data_loaded):

        canvas.paste(scoreboard.home_team_logo, (0,0))
        canvas.paste(scoreboard.away_team_logo, ((total_width_LEDboard - max_pixel_width_logos),0))
        
        if(scoreboard.state == "wait_next_game"):
            canvas.paste(scoreboard.gametime_img, ((total_width_LEDboard - scoreboard.gametime_img.size[0] ) // 2, int(total_height_LEDboard * 0.01)))
            # canvas.paste(scoreboard.gamedate_img, ((total_width_LEDboard - max_pixel_width_logos * 2) // 2 , int(total_height_LEDboard * 0.5)))
            canvas.paste(scoreboard.gamedate_img, ((total_width_LEDboard - scoreboard.gamedate_img.size[0]) // 2 , int(total_height_LEDboard * 0.5)))

        elif(scoreboard.state == "game_live"):
            canvas.paste(scoreboard.current_time_img, ((total_width_LEDboard - scoreboard.current_time_img.size[0]) // 2, int(total_height_LEDboard * 0.01)))
            print("in game_live")

        else:
            canvas.paste(scoreboard.score_img, ((total_width_LEDboard - scoreboard.score_img.size[0] -1) // 2 , int((total_height_LEDboard - scoreboard.score_img.size[1]) // 2)))
        
        framebuffer[:] = np.asarray(canvas)
        matrix.show();


# Das nächste anstehende Spiel des als Parameter zu übergebenden Teams der ebenfalls zu übergebenen Liga:

    # https://api.openligadb.de/getnextmatchbyleagueteam/3005/7

    # '3005' entspricht der LeagueId der 1. Fußball Bundesliga 2016/2017
    # '7' entspricht der TeamId von Borussia Dortmund

#
# 
#
#Weiterhin sollte in den Liga-Einstellungen zu jedem Ergebnis der Liga-übergreifendende Ergebnistyp festgelegt werden. Dieser ermöglicht es, in jeder Liga der OpenLigaDB beispielsweise nach der resultTypeID == 1 zu filtern und damit immer das Halbzeitergebnis zu ermitteln. So erfolgt auch basierend auf der resultTypeID == 2 die Berechnung der Punkte für die Bundesliga-Tabelle.
#
#Zur Abfrage eines spezifischen Ergebnistyps wird empfohlen, die "resultTypeID" zu verwenden und damit unabhängig von der Reihenfolge der matchResults-Elemente zu sein.
#