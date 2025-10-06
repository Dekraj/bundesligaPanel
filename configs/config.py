from PIL import ImageFont
import numpy as np
from PIL import Image

# 16 = VfB Stuttgart
my_team_id = 40

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

canvas = Image.new("RGB", (total_width_LEDboard,total_height_LEDboard), (0,0,0))
framebuffer = np.asarray(canvas) + 0



wochentage = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}
