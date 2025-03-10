import adafruit_htu21d
import adafruit_sgp4x
import adafruit_scd4x
import adafruit_bme680
import adafruit_ltr390
import adafruit_tsl2591
import adafruit_as7341
import adafruit_gps
import busio
import json
import time

class sensor_handler:
    def __init__(self, i2c_bus: busio.I2C, calib_file: str, logger) -> None:
        self._i2c_bus = i2c_bus
        self._logger = logger
        self._init = False
        self._devices = {}
        self._dict_keys = []
        # Sensor update 1HZ
        self.htu21_temp = 0
        self.htu21_hum = 0
        self.bme68x_temp = 0
        self.bme68x_hum = 0
        self.sgp4x_compensated_raw_gas = 0
        self.sgp4x_voc_index = 0
        self.pa1010_lat = None
        self.pa1010_long = None
        self.sensor_warm_up = False
        self.sensor_warm_up_10s = False
        self.sensor_warm_up_2min = False
        self.sensor_warm_up_time = 10*60 # 10min
        self.sensor_warm_up_time_10s = 10 # 10s
        self.sensor_warm_up_time_2min = 2*60 # 2min
        self.time_init = 0 
        try: # Load Sensor calibration Data / Offset
            with open(calib_file, "r") as f:
                self._sensor_calib = json.load(f)
                f.close()
        except Exception as e:
            self._logger.error("Failed to load calib_file. Error: %s\n", e)

    def init(self, log_interval):
        if self._i2c_bus.try_lock():
            addrs = self._i2c_bus.scan()
            self._i2c_bus.unlock()
            self.sensor_warm_up = False
            self.time_init = time.monotonic()
            if 0x10 in addrs: #16 pa1010
                self.pa1010 = adafruit_gps.GPS_GtopI2C(self._i2c_bus, debug=False)
                # Turn on the basic GGA and RMC info (what you typically want)
                self.pa1010.send_command(b"PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0")
                # Turn on just minimum info (RMC only, location):
                # self.pa1010.send_command(b'PMTK314,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0')
                # Turn on everything (not all of it is parsed!)
                # self.pa1010.send_command(b'PMTK314,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0')

                # Set update rate to once a second (1hz) which is what you typically want.
                # self.pa1010.send_command(b"PMTK220,1000")
                # Or decrease to once every two seconds by doubling the millisecond value.
                self.pa1010.send_command(b'PMTK220,2000')
                self._devices["pa1010"]=True
                self._dict_keys.append("pa1010_lat")
                self._dict_keys.append("pa1010_lon")
            else:
                self._devices["pa1010"]=False

            if 0x29 in addrs: #41 tsl2591
                self.tsl2591 = adafruit_tsl2591.TSL2591(self._i2c_bus) # Lux is not calibrated
                self.tsl2591.gain = adafruit_tsl2591.GAIN_LOW
                self.tsl2591.integration_time = adafruit_tsl2591.INTEGRATIONTIME_200MS
                self._devices["tsl2591"]=True
                self._dict_keys.append("tsl2591_lux")
                self._dict_keys.append("tsl2591_infrared")
                self._dict_keys.append("tsl2591_visible")
                self._dict_keys.append("tsl2591_full_spectrum")
            else:
                self._devices["tsl2591"]=False

#            if 0x39 in addrs: #57 as7341
#                self.as7341 = adafruit_as7341.AS7341(self._i2c_bus)
#                self.as7341.gain = adafruit_as7341.Gain.GAIN_1X
#                self._dict_keys.append("as7341_415nm")
#                self._dict_keys.append("as7341_445nm")
#                self._dict_keys.append("as7341_480nm")
#                self._dict_keys.append("as7341_515nm")
#                self._dict_keys.append("as7341_555nm")
#                self._dict_keys.append("as7341_590nm")
#                self._dict_keys.append("as7341_630nm")
#                self._dict_keys.append("as7341_680nm")
#                self._dict_keys.append("as7341_clear")
#                self._dict_keys.append("as7341_nir")
#                # self.as7341.led = False
#                #as7341.flicker_detection_enabled = True
#                self._devices["as7341"]=True
#            else:
            self._devices["as7341"]=False

            if 0x40 in addrs: #64 htu21
                self.htu21 = adafruit_htu21d.HTU21D(self._i2c_bus)
                self.htu21.temp_rh_resolution = 0 # 14-Bit (max)
                self._devices["htu21"]=True
                self._dict_keys.append("htu21_temperature")
                self._dict_keys.append("htu21_humidity")
            else:
                self._devices["htu21"]=False

            if 0x53 in addrs: #83 ltr390
                self.ltr390 = adafruit_ltr390.LTR390(self._i2c_bus)
                self.ltr390.gain = adafruit_ltr390.Gain.GAIN_1X
                self.ltr390.resolution = adafruit_ltr390.Resolution.RESOLUTION_20BIT
                self.ltr390.measurement_delay = adafruit_ltr390.MeasurementDelay.DELAY_2000MS
                self.ltr390.window_factor = 1 # no/clear Window
                self._devices["ltr390"]=True
                self._dict_keys.append("ltr390_light")
                self._dict_keys.append("ltr390_lux")
                self._dict_keys.append("ltr390_uvs")
                self._dict_keys.append("ltr390_uvi")
            else:
                self._devices["ltr390"]=False

            if 0x59 in addrs: #89 sgp40 0-500 VOC Index
                self.sgp4x = adafruit_sgp4x.SGP4x(self._i2c_bus)
                if self.sgp4x.getSGP4x() == adafruit_sgp4x._SGP40:
                    self._devices["sgp40"]=True
                    self._devices["sgp41"]=False
                    self._dict_keys.append("sgp4x_voc")
                    self._dict_keys.append("sgp4x_voc_raw")
                elif self.sgp4x.getSGP4x() == adafruit_sgp4x._SGP41:
                    self.sgp4x.execute_conditioning()
                    self._devices["sgp40"]=False
                    self._devices["sgp41"]=True
                    self._dict_keys.append("sgp4x_voc")
                    self._dict_keys.append("sgp4x_voc_raw")
            else:
                self._devices["sgp40"]=False
                self._devices["sgp41"]=False

            if 0x62 in addrs: #98 scd4x
                self.scd4x = adafruit_scd4x.SCD4X(self._i2c_bus)
                # scd4x.force_calibration(400) #Calibration Co2
                self.scd4x.self_calibration_enabled = True
                self.scd4x.temperature_offset = self._sensor_calib["scd4x_temp_Offset"]
                if log_interval > (30 + 5):
                    self.scd4x.start_low_periodic_measurement() #30s
                else:
                    self.scd4x.start_periodic_measurement() #5s
                self._devices["scd4x"]=True
                self._dict_keys.append("scd4x_co2")
                self._dict_keys.append("scd4x_temp")
                self._dict_keys.append("scd4x_hum")
            else:
                self._devices["scd4x"]=False

            if 0x77 in addrs: #119 bme68x
                self.bme680 = adafruit_bme680.Adafruit_BME680_I2C(self._i2c_bus, debug=False, refresh_rate = 1)
                self.bme680.sea_level_pressure = 1013.25
                self.bme680.humidity_oversample = 16
                self.bme680.temperature_oversample = 16
                self.bme680.pressure_oversample = 16
                self.bme680.filter_size = 127
                self._devices["bme68x"]=True
                self._dict_keys.append("bme68x_temperature")
                self._dict_keys.append("bme68x_humidity")
                self._dict_keys.append("bme68x_gas")
                self._dict_keys.append("bme68x_pressure")
            else:
                self._devices["bme68x"]=False
            self._logger.info("I2C Scan: %s\n",json.dumps(self._devices))
        return [self._devices, self._dict_keys]

    def update_1hz(self):
        if self._devices["htu21"]:
            self.htu21_temp = self.htu21.temperature + self._sensor_calib["htu21_temp_Offset"]
            self.htu21_hum  = self.htu21.relative_humidity + self._sensor_calib["htu21_hum_Offset"]
        if self._devices["sgp40"] or self._devices["sgp41"]: # Has to update every second (sampling rate 1 Hz)
            if self._devices["htu21"]:
                self.sgp4x_compensated_raw_gas = self.sgp4x.measure_raw(temperature=self.htu21_temp, relative_humidity=self.htu21_hum) + self._sensor_calib["sgp4x_compensated_raw_gas_Offset"]
                self.sgp4x_voc_index = self.sgp4x.measure_index(temperature=self.htu21_temp, relative_humidity=self.htu21_hum) + self._sensor_calib["sgp4x_voc_index_Offset"]
            elif self._devices["bme68x"]:
                self.sgp4x_compensated_raw_gas = self.sgp4x.measure_raw(temperature=self.bme68x_temp, relative_humidity=self.bme68x_hum) + self._sensor_calib["sgp4x_compensated_raw_gas_Offset"]
                self.sgp4x_voc_index = self.sgp4x.measure_index(temperature=self.bme68x_temp, relative_humidity=self.bme68x_hum) + self._sensor_calib["sgp4x_voc_index_Offset"]
            else:
                self.sgp4x_compensated_raw_gas = self.sgp4x.measure_raw() + self._sensor_calib["sgp4x_compensated_raw_gas_Offset"]
                self.sgp4x_voc_index = self.sgp4x.measure_index() + self._sensor_calib["sgp4x_voc_index_Offset"]

        if self._devices["pa1010"]:
            self.pa1010.update()
            if self.pa1010.has_fix:
                self.pa1010_lat  = "{0:.6f}".format(self.pa1010.latitude)
                self.pa1010_long = "{0:.6f}".format(self.pa1010.longitude)
    
    def read_sensor(self):
        if self._devices["as7341"]:
            as7341_channel_415nm = self.as7341.channel_415nm + self._sensor_calib["as7341_415nm_Offset"]
            as7341_channel_445nm = self.as7341.channel_445nm + self._sensor_calib["as7341_445nm_Offset"]
            as7341_channel_480nm = self.as7341.channel_480nm + self._sensor_calib["as7341_480nm_Offset"]
            as7341_channel_515nm = self.as7341.channel_515nm + self._sensor_calib["as7341_515nm_Offset"]
            as7341_channel_555nm = self.as7341.channel_555nm + self._sensor_calib["as7341_555nm_Offset"]
            as7341_channel_590nm = self.as7341.channel_590nm + self._sensor_calib["as7341_590nm_Offset"]
            as7341_channel_630nm = self.as7341.channel_630nm + self._sensor_calib["as7341_630nm_Offset"]
            as7341_channel_680nm = self.as7341.channel_680nm + self._sensor_calib["as7341_680nm_Offset"]
            as7341_channel_clear = self.as7341.channel_clear + self._sensor_calib["as7341_clear_Offset"]
            as7341_channel_nir   = self.as7341.channel_nir + self._sensor_calib["as7341_nir_Offset"]
            #as7341_flicker_detected   = as7341.flicker_detected
            
        if self._devices["ltr390"]:
            ltr390_light = self.ltr390.light + self._sensor_calib["ltr390_light_Offset"]   #currently measured ambient light level
            ltr390_lux   = self.ltr390.lux + self._sensor_calib["ltr390_lux_Offset"]       #calculated Lux value
            ltr390_uvs   = self.ltr390.uvs + self._sensor_calib["ltr390_uvs_Offset"]       #calculated UV value
            ltr390_uvi   = self.ltr390.uvi + self._sensor_calib["ltr390_uvi_Offset"]       #UV Index (UVI)

        if self._devices["tsl2591"]:
            tsl2591_infrared  = self.tsl2591.infrared + self._sensor_calib["tsl2591_infrared_Offset"]
            tsl2591_visible   = self.tsl2591.visible + self._sensor_calib["tsl2591_visible_Offset"]
            tsl2591_full_spectrum = self.tsl2591.full_spectrum + self._sensor_calib["tsl2591_full_spectrum_Offset"]
            try: # Ignore Error: Overflow reading light channels
                tsl2591_lux = self.tsl2591.lux + self._sensor_calib["tsl2591_lux_Offset"]
            except Exception as e:
                  self._logger.error("tsl2591 read Error: %s\n",e)
                  tsl2591_lux = None         

        if self._devices["bme68x"]:
            bme68x_temp = self.bme680.temperature + self._sensor_calib["bme68x_temp_Offset"]
            bme68x_hum  = self.bme680.relative_humidity  + self._sensor_calib["bme68x_hum_Offset"]
            bme68x_gas  = self.bme680.gas  + self._sensor_calib["bme68x_gas_Offset"]
            bme68x_pres = self.bme680.pressure  + self._sensor_calib["bme68x_pres_Offset"]
            #bme68x_alt  = self.bme680.altitude  + self._sensor_calib["bme68x_alt_Offset"]

        if self._devices["scd4x"]:
            if self.scd4x.data_ready:
                self.scd4x.set_ambient_pressure(int(bme68x_pres))
                scd4x_co2 = self.scd4x.CO2 + self._sensor_calib["scd4x_co2_Offset"]
                scd4x_temp = self.scd4x.temperature 
                scd4x_hum = self.scd4x.relative_humidity  + self._sensor_calib["scd4x_hum_Offset"]
            else:
                scd4x_co2 = None

        if not self.sensor_warm_up:
            if (time.monotonic()-self.time_init) >= self.sensor_warm_up_time:
                self.sensor_warm_up = True
        if not self.sensor_warm_up_10s:
            if (time.monotonic()-self.time_init) >= self.sensor_warm_up_time_10s:
                self.sensor_warm_up_10s = True
        if not self.sensor_warm_up_2min:
            if (time.monotonic()-self.time_init) >= self.sensor_warm_up_time_2min:
                self.sensor_warm_up_2min = True
        data={}

        if self._devices["ltr390"]:
            data["ltr390_light"]          = ltr390_light
            data["ltr390_lux"]            = ltr390_lux
            data["ltr390_uvs"]            = ltr390_uvs
            data["ltr390_uvi"]            = ltr390_uvi
        if self._devices["tsl2591"]:
            if tsl2591_lux is not None:
                data["tsl2591_lux"]       = tsl2591_lux
            data["tsl2591_infrared"]      = tsl2591_infrared
            data["tsl2591_visible"]       = tsl2591_visible
            data["tsl2591_full_spectrum"] = tsl2591_full_spectrum
        if self._devices["htu21"]:
            data["htu21_temperature"]     = self.htu21_temp
            data["htu21_humidity"]        = self.htu21_hum
        if self._devices["bme68x"] and self.sensor_warm_up:
            data["bme68x_temperature"]    = bme68x_temp
            data["bme68x_humidity"]       = bme68x_hum
            data["bme68x_gas"]            = bme68x_gas
            data["bme68x_pressure"]       = bme68x_pres
            #data["bme68x_altitude"]      = bme68x_alt
        if self._devices["sgp40"] and self.sensor_warm_up_2min:
            data["sgp40_voc"]             = self.sgp4x_voc_index
            data["sgp40_compensated_raw_gas"]= self.sgp4x_compensated_raw_gas
        if self._devices["sgp41"] and self.sensor_warm_up_2min:
            data["sgp41_voc"]             = self.sgp4x_voc_index
            data["sgp41_compensated_raw_gas"]= self.sgp4x_compensated_raw_gas
        if self._devices["scd4x"] and (scd4x_co2 is not None):
            data["scd4x_co2"]             = scd4x_co2
            data["scd4x_temp"]            = scd4x_temp
            data["scd4x_hum"]             = scd4x_hum
        if self._devices["pa1010"]:
            if self.pa1010.has_fix:
                data["pa1010_lat"]        = self.pa1010_lat
                data["pa1010_lon"]        = self.pa1010_long
        if self._devices["as7341"]:
            data["as7341_415nm"]          = as7341_channel_415nm
            data["as7341_445nm"]          = as7341_channel_445nm
            data["as7341_480nm"]          = as7341_channel_480nm
            data["as7341_515nm"]          = as7341_channel_515nm
            data["as7341_555nm"]          = as7341_channel_555nm
            data["as7341_590nm"]          = as7341_channel_590nm
            data["as7341_630nm"]          = as7341_channel_630nm
            data["as7341_680nm"]          = as7341_channel_680nm
            data["as7341_clear"]          = as7341_channel_clear
            data["as7341_nir"]            = as7341_channel_nir
            #data["as7341_flicker"]   = as7341_flicker_detected
        return data