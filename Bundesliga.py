import numpy as np
import adafruit_blinka_raspberry_pi5_piomatter as piomatter
from classes.Scoreboard import Scoreboard
from configs import config

#
# To display the gameplan of your team
# change the team_id in config.py
# the team_id can be found on https://www.openligadb.de/
#

geometry = piomatter.Geometry(width=config.total_width_LEDboard, height=config.total_height_LEDboard,
                              n_addr_lines=4, rotation=piomatter.Orientation.Normal)
matrix = piomatter.PioMatter(colorspace=piomatter.Colorspace.RGB888Packed,
                             pinout=piomatter.Pinout.AdafruitMatrixBonnet,
                             framebuffer=config.framebuffer,
                             geometry=geometry)

scoreboard = Scoreboard()

while True:

    if(scoreboard.data_loaded):

        config.canvas.paste(scoreboard.home_team_logo, (0,0))
        config.canvas.paste(scoreboard.away_team_logo, ((config.total_width_LEDboard - config.max_pixel_width_logos),0))
        
        if(scoreboard.state == "wait_next_game"):
            config.canvas.paste(scoreboard.gametime_img, ((config.total_width_LEDboard - scoreboard.gametime_img.size[0] ) // 2, int(config.total_height_LEDboard * 0.01)))
            # canvas.paste(scoreboard.gamedate_img, ((total_width_LEDboard - max_pixel_width_logos * 2) // 2 , int(total_height_LEDboard * 0.5)))
            config.canvas.paste(scoreboard.gamedate_img, ((config.total_width_LEDboard - scoreboard.gamedate_img.size[0]) // 2 , int(config.total_height_LEDboard * 0.5)))

        elif(scoreboard.state == "game_live"):
            config.canvas.paste(scoreboard.current_time_img, ((config.total_width_LEDboard - scoreboard.current_time_img.size[0]) // 2, int(config.total_height_LEDboard * 0.01)))
            config.canvas.paste(scoreboard.score_img,((config.total_width_LEDboard - scoreboard.score_img.size[0]) // 2, int(config.total_height_LEDboard * 0.5)))

        else:
            config.canvas.paste(scoreboard.current_time_img, ((config.total_width_LEDboard - scoreboard.current_time_img.size[0] -1) // 2 , int((config.total_height_LEDboard * 0.01))))
            config.canvas.paste(scoreboard.score_img, ((config.total_width_LEDboard - scoreboard.score_img.size[0] -1) // 2 , int((config.total_height_LEDboard * 0.5))))
        
        config.framebuffer[:] = np.asarray(config.canvas)
        matrix.show()