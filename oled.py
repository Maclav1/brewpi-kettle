import board
import digitalio
from PIL import Image, ImageDraw, ImageFont
import adafruit_ssd1306
from config import Conf


class oled:
    i2c = board.I2C()
    oled_reset = digitalio.DigitalInOut(board.D4)
    oled = adafruit_ssd1306.SSD1306_I2C(Conf.oled_width, Conf.oled_height, i2c, addr=Conf.oled_addr, reset=oled_reset)
    font = ImageFont.truetype(Conf.oled_font, Conf.oled_font_size)

    def writeText(self, text):
        self.oled.fill(0)
        image = Image.new("1", (self.oled.width, self.oled.height))
        draw = ImageDraw.Draw(image)
        draw.text((0, 0), text, font=self.font, fill=255)
        self.oled.image(image)
        self.oled.show()
