import numpy as np
import requests
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageDraw
import random
from configs import config
from io import BytesIO
from wand.image import Image as WandImage
from wand.color import Color

def clearBoard():
    config.canvas.paste((0,0,0), [0,0,config.canvas.width, config.canvas.height])
    config.framebuffer[:] = np.asarray(config.canvas)                         

def getNextMatch():
    data = requests.get("https://api.openligadb.de/getmatchdata/bl1/2025/").json()
    # data = requests.get("https://api.openligadb.de/getmatchdata/25testmqtt/2025/").json()
    filtered = [row for row in data if row["team1"]["teamId"] == config.my_team_id or row["team2"]["teamId"] == config.my_team_id]
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
    data = requests.get('https://api.openligadb.de/getmatchdata/bl1/2025/'+ str(gameday)).json()
    # data = requests.get('https://api.openligadb.de/getmatchdata/25testmqtt/2025/'+ str(gameday)).json()
    filtered = [row for row in data if row["team1"]["teamId"] == config.my_team_id or row["team2"]["teamId"] == config.my_team_id]
    return filtered

def make_text_img(text, font, font_color, padding = [0,0,0,0]):
    top, right, bottom, left = padding
    x,y,width,height = font.getbbox(text) 
    text_img = Image.new("RGB", (int(width + right + left), int(height + top + bottom)),(0,0,0)) 
    draw = ImageDraw.Draw(text_img) 
    draw.text((left,top),text, font=font, fill=font_color) 
    return text_img

def generate_overtime():
    # Currently its not possible to fetch the overtime via the API
    # so we guess the overtime
    over_time_minutes = [1,2,3,4,5,6,7] 
    weights = [0.03, 0.22, 0.25, 0.22, 0.17, 0.1, 0.01]
    over_time = random.choices(over_time_minutes, weights=weights, k=1)[0]
    return over_time 

def svg_to_png(svg_bytes):
    with WandImage(blob=svg_bytes, format='svg') as wand_img:
        
        wand_img.background_color = 'transparent'  # Wichtig: transparent
        wand_img.alpha_channel = 'activate'  
        png_bytes = wand_img.make_blob(format='png')
    pil_img = Image.open(BytesIO(png_bytes))

    return pil_img

def load_team_logo(url):
    response = requests.get(url, headers=config.headers)    
    if url.lower().endswith(".svg"):
        return svg_to_png(response.content)
    else:
        return Image.open(BytesIO(response.content))