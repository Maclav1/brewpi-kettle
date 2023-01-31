import board
import digitalio
from PIL import Image, ImageDraw, ImageFont
import adafruit_ssd1306
import logging

class oled:
    WIDTH = 128
    HEIGHT = 64 
    ADDR = 0x3C
    i2c = board.I2C()    
    oled_reset = digitalio.DigitalInOut(board.D4)
    oled = adafruit_ssd1306.SSD1306_I2C(WIDTH, HEIGHT, i2c, addr=ADDR, reset=oled_reset)
    #font = ImageFont.truetype("DejaVuSansMono.ttf", 12)
    #font = ImageFont.load_default()
    font = ImageFont.truetype("/DejaVuSansMono.ttf", 14)

    def writeText(self, text):
        #logging.debug(f'Printing to oLed')
        self.oled.fill(0)
        #self.oled.show()
        image = Image.new("1", (self.oled.width, self.oled.height))
        draw = ImageDraw.Draw(image)
        #(font_width, font_height) = font.getsize(text)
        draw.text((0,0), text, font=self.font, fill=255)
        self.oled.image(image)
        self.oled.show()
