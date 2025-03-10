import board
import displayio
import busio
import time
import terminalio
from adafruit_display_text import bitmap_label


class display_handler:
    def __init__(self, uid: str)  -> None:
        self.uid = uid
        self.display = None
        self.main_group = None
        self.boot_group = None
        self.init_group = None
        self.data_group = None
        self.diplaytoggeltime = 5 
        self.lastTimeValueChange = 0 
        self.nextValue = 0
        self.initDisplay()

    def initDisplay(self):
        if "DISPLAY" in dir(board):
            self.display = board.DISPLAY
        if self.display is None:
            displayio.release_displays()
            if board.board_id == "lolin_s2_pico":  # lolin_s2_pico OLED display ssd1306 
                import adafruit_displayio_ssd1306 
                oled_reset = board.IO18
                i2c_disp = busio.I2C(sda=board.IO8, scl=board.IO9)
                display_bus = displayio.I2CDisplay(
                    i2c_disp, device_address=0x3C, reset=oled_reset
                )
                WIDTH = 128
                HEIGHT = 32
                self.display = adafruit_displayio_ssd1306.SSD1306(
                    display_bus, width=WIDTH, height=HEIGHT
                )
            elif board.board_id == "waveshare_esp32_s2_pico_lcd": # waveshare_esp32_s2_pico TFT display st7735r
                import adafruit_st7735r
                tft_cs = board.LCD_CS
                tft_dc = board.LCD_DC
                tft_rst = board.LCD_RST
                tft_bl = board.LCD_BACKLIGHT
                spi_disp = busio.SPI(clock=board.LCD_CLK, MOSI=board.LCD_MOSI)
                display_bus = displayio.FourWire(spi_disp, command=tft_dc, chip_select=tft_cs, reset=tft_rst)
                display_bus.reset()
                WIDTH = 160
                HEIGHT = 80
                self.display = adafruit_st7735r.ST7735R(display_bus, backlight_pin=tft_bl, bgr=False, width=WIDTH, height=HEIGHT, rotation=90, colstart=26, rowstart=1, invert=True)
            elif board.board_id == "waveshare_esp32_s2_pico": # waveshare_esp32_s2_pico TFT display st7735r
                import adafruit_st7735r
                tft_cs = board.LCD_CS
                tft_dc = board.LCD_DC
                tft_rst = board.LCD_RST
                tft_bl = board.LCD_BACKLIGHT
                spi_disp = busio.SPI(clock=board.LCD_CLK, MOSI=board.LCD_MOSI)
                display_bus = displayio.FourWire(spi_disp, command=tft_dc, chip_select=tft_cs, reset=tft_rst)
                display_bus.reset()
                WIDTH = 160
                HEIGHT = 80
                self.display = adafruit_st7735r.ST7735R(display_bus, backlight_pin=tft_bl, bgr=False, width=WIDTH, height=HEIGHT, rotation=90, colstart=26, rowstart=1, invert=True)
            else:
                self.display = None
        if (self.display is not None):
            self.main_group = displayio.Group()
            self.display.show(self.main_group)

    def showBootScreen(self):
        if self.display is not None:
            if self.boot_group is None:
                self.boot_group = displayio.Group()
                try:
                    bitmap = displayio.OnDiskBitmap("/boot.bmp")
                    if (bitmap.width < self.display.width) or (bitmap.height < self.display.height):
                        boot_bmp = displayio.TileGrid(bitmap, pixel_shader=bitmap.pixel_shader)
                        boot_bmp.x = int((self.display.width-bitmap.width)/2)
                        boot_bmp.y = int((self.display.height-bitmap.height)/2)
                        self.boot_group.append(boot_bmp)
                except:
                    pass
                text = ("UID: %s" % self.uid)
                uid_lable = bitmap_label.Label(font=terminalio.FONT, text=text, scale=1)
                uid_lable.anchor_point = (0.5, 1)
                uid_lable.anchored_position = (self.display.width/2, self.display.height-4)
                self.boot_group.append(uid_lable)
            self.main_group.insert(0,self.boot_group)

    def showInitText(self, line1:str ="", line2:str ="", line3:str =""):
        if self.display is not None:
            if self.init_group is None:
                self.main_group.pop()
                self.init_group = displayio.Group()
                text = ("UID: %s" % self.uid)
                uid_lable = bitmap_label.Label(font=terminalio.FONT, text=text, scale=1)
                uid_lable.color=0x14639e
                uid_lable.anchor_point = (0, 1)
                uid_lable.anchored_position = (2, self.display.height-2)
                self.init_lable_1 = bitmap_label.Label(font=terminalio.FONT, scale=1)
                self.init_lable_1.anchor_point = (0, 0)
                self.init_lable_1.anchored_position = (2, 2)
                self.init_group.append(uid_lable)
                self.init_group.append(self.init_lable_1)
                self.main_group.insert(0,self.init_group)
            self.init_lable_1.text = (line1 + "\n" + line2 + "\n" + line3)

    def displayOn(self, on:bool=True):
        if on and self.display.brightness is not 1.0:
            self.display.brightness = 1.0
        elif not on and self.display.brightness is not 0.0:
            self.main_group.pop()
            self.display.brightness = 0.0

    def showSensorValues(self, co2:float = None, temp:float=None, hum:float=None, voc:float=None, lux:float=None):
        if self.display is not None:
            if self.data_group is None:
                self.main_group.pop()
                self.data_group = displayio.Group()
                self.sensor_value = bitmap_label.Label(terminalio.FONT, scale=4, base_alignment=True)
                self.sensor_value.anchor_point = (1, 0.5)
                self.sensor_value.anchored_position = (int(self.display.width*(3/4)), int(self.display.height/2))
                self.data_group.append(self.sensor_value)
                self.sensor_unit = bitmap_label.Label(terminalio.FONT, scale=2, base_alignment=True)
                self.sensor_unit.anchor_point = (0, 0.5)
                self.sensor_unit.anchored_position = (int(self.display.width*(3/4) + 4), int(self.display.height/2) + 9)   
                self.data_group.append(self.sensor_unit)
                self.main_group.insert(0,self.data_group)

            if time.monotonic() > self.diplaytoggeltime + self.lastTimeValueChange:
                self.lastTimeValueChange = time.monotonic()
                counts = 0
                while (counts <= 2):
                    if self.nextValue is 0:
                        self.nextValue = 1
                        if co2 is not None:
                            self._showCO2(co2)
                            break
                    if self.nextValue is 1:
                        self.nextValue = 2
                        if temp is not None:
                            self._showTemp(temp)
                            break
                    if self.nextValue is 2:
                        self.nextValue = 3
                        if hum is not None:
                            self._showHum(hum)
                            break
                    if self.nextValue is 3:
                        self.nextValue = 4
                        if voc is not None:
                            self._showVoc(voc)
                            break
                    if self.nextValue is 4:
                        self.nextValue = 0
                        if lux is not None:
                            self._showLux(lux)
                            break
                    counts = counts + 1

    def _showCO2(self, co2:float):
        self.sensor_value.text = "%4u" % (co2)
        self.sensor_unit.text = "ppm"

    def _showTemp(self, temp:float):
        self.sensor_value.text = "%3.1f" % (temp)
        #self.sensor_unit.text = "°C"
        self.sensor_unit.text = "C"

    def _showHum(self, hum:float):
        self.sensor_value.text = "%4.1f" % (hum)
        self.sensor_unit.text = "%"

    def _showVoc(self, voc:float):
        self.sensor_value.text = "%3u" % (voc)
        self.sensor_unit.text = "voc"

    def _showLux(self, lux:float):
        self.sensor_value.text = "%5u" % (lux)
        self.sensor_unit.text = "lx"