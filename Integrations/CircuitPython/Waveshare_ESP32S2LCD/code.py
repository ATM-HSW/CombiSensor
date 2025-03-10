import board
import microcontroller
import time
import alarm
import busio
import analogio
from digitalio import DigitalInOut, Direction, Pull
from adafruit_debouncer import Button
import binascii
import socketpool
import ssl
import rtc
import sys
import json
import wifi
import watchdog
import traceback
import supervisor
import adafruit_requests
import adafruit_ntp
import adafruit_logging

import sensor_handler
import display_handler
import csv_handler
__version__ = "1.1.0"
__repo__ = "https://github.com/ATM-HSW/CircuitPython_RaumSensor.git"

config_file = "/config.json"
calib_file = "/sensor_calibration.json"
enable_wifi = False
tb_enable = False
nr_enable = False
mqtt_enable = False
socket_pool = None
request_session = None
uid = binascii.hexlify(microcontroller.cpu.uid).decode("utf-8")
wdt = microcontroller.watchdog



log = adafruit_logging.getLogger("main")
log.addHandler(adafruit_logging.StreamHandler())
log.setLevel(adafruit_logging.DEBUG)

try:  # Watchdog, global Errors
    disp=display_handler.display_handler(uid)
    disp.showBootScreen()
    try:
        with open(config_file, "r") as f:
            config = json.load(f)
            f.close()
            enable_display = config["enable_display"]
            enable_wdt = config["enable_wdt"]
            enable_csv = config["enable_csv"]
            log_interval = config["log_interval"]
            enable_wifi = config["enable_wifi"]
            tb_enable = config["thingsboard"]
            tb_host = config["thingsboard_host"]
            tb_ssl = config["thingsboard_ssl"]
            tb_device = config["thingsboard_device"]
            nr_enable = config["nodered"]
            nr_host = config["nodered_host"]
            nr_ssl = config["nodered_ssl"]
            nr_user = config["nodered_user"]
            nr_pass = config["nodered_pass"]
            nr_mqtt_topic = config["topic"]
            mqtt_enable = config["mqtt"]
            mqtt_host = config["mqtt_host"]
            mqtt_port = config["mqtt_port"]
            mqtt_ssl = config["mqtt_ssl"]
            mqtt_user = config["mqtt_user"]
            mqtt_pass = config["mqtt_pass"]
            full_topic = "%s/%s" % (nr_mqtt_topic, uid)
    except Exception as e:
        log.error("Failed to load config file, switch off wifi: %s\n", e)
        traceback.print_exception(None, e, e.__traceback__)
        enable_wifi = False
        tb_enable = False
        nr_enable = False
        mqtt_enable = False
        log_interval = 20

    if enable_wdt:
        wdt.timeout = log_interval + 10
        wdt.mode = watchdog.WatchDogMode.RAISE
        wdt.feed()

    # Imports
    if enable_wifi:
        from wifi_manager import WifiManager
    if tb_enable:
        import ThingsBoard
    if nr_enable:
        import nodeRed_MQTT
    if mqtt_enable:
        import adafruit_minimqtt.adafruit_minimqtt as MQTT

    if board.board_id == "lolin_s2_pico":
        vbat_adc = None
        sens_sda = board.IO37
        sens_scl = board.IO38
    elif board.board_id == "waveshare_esp32_s2_pico_lcd":
#        vbat_adc = analogio.AnalogIn(board.USB_IN)
        vbat_adc = None
        sens_sda = board.GP15
        sens_scl = board.GP14
    elif board.board_id == "waveshare_esp32_s2_pico":
#        vbat_adc = analogio.AnalogIn(board.USB_IN)
        vbat_adc = None
        #sens_sda = board.GP15
        #sens_scl = board.GP14
        sens_sda = board.IO15
        sens_scl = board.IO14
        btn1 = DigitalInOut(board.IO38)
        btn1.direction = Direction.INPUT
        button1 = Button(btn1, value_when_pressed=True)
        btn2 = DigitalInOut(board.IO39)
        btn2.direction = Direction.INPUT
        button2 = Button(btn2, value_when_pressed=True)
    else:
        log.error("Board %s not configured!\n" % board.board_id)
        vbat_adc = None
        sens_sda = board.SDA
        sens_scl = board.SCL
        time.sleep(60)
        microcontroller.reset()
    log.debug("%s Board Init, UID: %s\n", board.board_id, uid)

    time.sleep(5) # show Bootscreen

    log.debug("I2C SensorInit\n")
    disp.showInitText("I2C SensorInit...")
    i2c_sens = busio.I2C(sda=sens_sda, scl=sens_scl)
    
    if i2c_sens.try_lock():
        buf = bytearray(1)
        buf[0] = 0x07 # Sensorboard Main (0x01),       GPS (0x02), QWIIC (0x04)
        #buf[0] = 0x0f # Sensorboard Main (0x01, 0x8) , GPS (0x02), QWIIC (0x04)
        try:
            i2c_sens.writeto(113, buf)
        except:
            print("no mux")
        i2c_sens.unlock()

    
    sensor = sensor_handler.sensor_handler(i2c_sens, calib_file, log)
    [devices, dict_keys] = sensor.init(log_interval)
    disp.showInitText("I2C SensorInit... OK!")
    time.sleep(2)
    csv = csv_handler.csv_handler(uid,dict_keys)

    if enable_wifi:
        log.debug("Wifi Init\n")
        disp.showInitText("Wifi connect...")
        try:
            ret = WifiManager.setup_network()
        except OSError as e:
            log.error("OSError wifi: %s\n", e)
            traceback.print_exception(None, e, e.__traceback__)
            time.sleep(10)
            microcontroller.reset()
        except RuntimeError as e:
            log.error("RuntimeError wifi: %s\n", e)
            traceback.print_exception(None, e, e.__traceback__)
            time.sleep(10)
            microcontroller.reset()
        if ret:
            log.debug("Wifi Connected to: %s\n", WifiManager.ssid)
            disp.showInitText("Wifi connect... OK!","connected to:", WifiManager.ssid)

            time.sleep(3)
            # create global socket pool
            socket_pool = socketpool.SocketPool(wifi.radio)
            request_session = adafruit_requests.Session(
                socket_pool, ssl.create_default_context()
            )
            try:
                # get utc time from timeserver
                ntp = adafruit_ntp.NTP(socket_pool, tz_offset=0)
                rtc.RTC().datetime = ntp.datetime  # set rtc time
            except OSError as e:
                log.error("OSError ntp: %s\n", e)
                traceback.print_exception(None, e, e.__traceback__)
            except RuntimeError as e:
                log.error("RuntimeError ntp: %s\n", e)
                traceback.print_exception(None, e, e.__traceback__)
        else:
            tb_enable = False
            nr_enable = False
            mqtt_enable = False
            if enable_wifi:
                log.error("Wifi Error! No connection\n")
                disp.showInitText("Wifi connect... ERROR!")
                time.sleep(30)
                microcontroller.reset()
    else:
        tb_enable = False
        nr_enable = False
        mqtt_enable = False

    if enable_wdt:
        wdt.feed()

    # TB Init
    if tb_enable:
        try:
            log.debug("ThingsBoard Init: %s\n", tb_host)
            disp.showInitText("ThingsBoard Init...", tb_host)
            tb = ThingsBoard.TBDeviceHttpClient(
                tb_host, tb_device, ssl=tb_ssl, request_session=request_session
            )
            if tb.connect():
                disp.showInitText("ThingsBoard Init... OK!", tb_host)
            else: 
                disp.showInitText("ThingsBoard Init... ERROR!", tb_host)
        except OSError as e:
            log.error("OSError tb: %s\n", e)
            traceback.print_exception(None, e, e.__traceback__)
            time.sleep(10)
            microcontroller.reset()
        except RuntimeError as e:
            log.error("RuntimeError tb: %s\n", e)
            traceback.print_exception(None, e, e.__traceback__)
            time.sleep(10)
            microcontroller.reset()
        try:
            log.debug("ThingsBoard send attributes\n")
            ret = tb.send_attributes(devices)
        except OSError as e:
            log.error("OSError tb: %s\n", e)
            traceback.print_exception(None, e, e.__traceback__)
            time.sleep(10)
            microcontroller.reset()
        except RuntimeError as e:
            log.error("RuntimeError tb: %s\n", e)
            traceback.print_exception(None, e, e.__traceback__)
            time.sleep(10)
            microcontroller.reset()
        try:
            version = (
                sys.implementation.name
                + " v"
                + str(sys.implementation.version[0])
                + "."
                + str(sys.implementation.version[1])
                + "."
                + str(sys.implementation.version[2])
                + ", mpy v"
                + str(sys.implementation.mpy)
            )
            board = board.board_id
            ret = tb.send_attributes(
                {
                    "main": __version__,
                    "ThingsBoard": ThingsBoard.__version__,
                    "version": version,
                    "board": board,
                    "device_id": uid,
                }
            )
        except OSError as e:
            log.error("OSError tb: %s\n", e)
            traceback.print_exception(None, e, e.__traceback__)
            time.sleep(10)
            microcontroller.reset()
        except RuntimeError as e:
            log.error("RuntimeError tb: %s\n", e)
            traceback.print_exception(None, e, e.__traceback__)
            time.sleep(10)
            microcontroller.reset()

        try:
            log.debug("ThingsBoard request attributes\n")
            ret = tb.request_attributes(devices)
        except OSError as e:
            log.error("OSError tb: %s\n", e)
            traceback.print_exception(None, e, e.__traceback__)
            time.sleep(10)
            microcontroller.reset()
        except RuntimeError as e:
            log.error("RuntimeError tb: %s\n", e)
            traceback.print_exception(None, e, e.__traceback__)
            time.sleep(10)
            microcontroller.reset()
    disp.showInitText("ThingsBoard Init... OK!")

    # Node.RED http request
    if nr_enable:
        try:
            disp.showInitText("NodeRed Init...", nr_host)
            log.debug("NodeRed Init: %s\n", nr_host)
            nr = nodeRed_MQTT.NRDeviceHttpMQTTClient(
                nr_host,
                uid,
                nr_ssl,
                request_session,
                username=nr_user,
                password=nr_pass,
            )
            if nr.connect():
                disp.showInitText("NodeRed Init... OK!", nr_host)
            else:
                disp.showInitText("NodeRed Init... ERROR!", nr_host)
        except OSError as e:
            log.error("OSError nr: %s\n", e)
            traceback.print_exception(None, e, e.__traceback__)
            time.sleep(10)
            microcontroller.reset()
        except RuntimeError as e:
            log.error("RuntimeError nr: %s\n", e)
            traceback.print_exception(None, e, e.__traceback__)
            time.sleep(10)
            microcontroller.reset()

    # MQTT enable
    if mqtt_enable:
        log.debug("MQTT Init: %s\n", mqtt_host)
        disp.showInitText("MQTT Init...", mqtt_host)
        mqtt_client = MQTT.MQTT(
            broker=mqtt_host,
            port=mqtt_port,
            username=mqtt_user,
            password=mqtt_pass,
            client_id=uid,
            socket_pool=socket_pool,
            is_ssl=mqtt_ssl,
            ssl_context=ssl.create_default_context(),
        )
        try:
            if mqtt_client.connect():
                disp.showInitText("MQTT Init... OK!", mqtt_host)
            else: 
                disp.showInitText("MQTT Init... ERROR!", mqtt_host)
        except OSError as e:
            log.error("OSError mqtt: %s\n", e)
            traceback.print_exception(None, e, e.__traceback__)
            time.sleep(10)
            microcontroller.reset()
        except RuntimeError as e:
            log.error("RuntimeError mqtt: %s\n", e)
            traceback.print_exception(None, e, e.__traceback__)
            time.sleep(10)
            microcontroller.reset()


    disp.displayOn(enable_display)

    log.debug("Start reading i2c-Sensors with time interval %i seconds\n", log_interval)
    tb_error_counter = 0
    nr_error_counter = 0
    mqtt_error_counter = 0
    max_errors = 10
    time_old = 0
    time_new = time_old
    time_ms_old = 0
    time_ms_new = time_ms_old
    data={}
    button1_pressed = False
    button1_long_press = False
    button2_pressed = False
    button2_long_press = False
    while True:  # Sensor read loop
        if enable_wdt:
            wdt.feed()
        time_new = time.monotonic()
        time_alarm = alarm.time.TimeAlarm(monotonic_time=time_new + 0.05)  # 1 Hz
        time_ms_new = supervisor.ticks_ms()
        if (time_ms_old + 1000) < time_ms_new:
            sensor.update_1hz()
            time_ms_old = time_ms_new
        button1.update()
        button2.update()
        if button1.pressed:
            button1_pressed = True
        elif button1.long_press:
            button1_long_press = True
        if button2.pressed:
            button2_pressed = True
        elif button2.long_press:
            button2_long_press = True

        if enable_display:
            if data.get("htu21_temperature", None) != None:
                if data.get("sgp40_voc", None) != None:
                    disp.showSensorValues(data.get("scd4x_co2", None), data.get("htu21_temperature", None), data.get("htu21_humidity", None), data.get("sgp40_voc", None), data.get("ltr390_lux", None))
                elif data.get("sgp41_voc", None) != None:
                    disp.showSensorValues(data.get("scd4x_co2", None), data.get("htu21_temperature", None), data.get("htu21_humidity", None), data.get("sgp41_voc", None), data.get("ltr390_lux", None))
            elif data.get("bme68x_temperature", None) != None:
                if data.get("sgp40_voc", None) != None:
                    disp.showSensorValues(data.get("scd4x_co2", None), data.get("bme68x_temperature", None), data.get("bme68x_humidity", None), data.get("sgp40_voc", None), data.get("ltr390_lux", None))
                elif data.get("sgp41_voc", None) != None:
                    disp.showSensorValues(data.get("scd4x_co2", None), data.get("bme68x_temperature", None), data.get("bme68x_humidity", None), data.get("sgp41_voc", None), data.get("ltr390_lux", None))
            else:
                if data.get("sgp40_voc", None) != None:
                    disp.showSensorValues(data.get("scd4x_co2", None), None, None, data.get("sgp40_voc", None), data.get("ltr390_lux", None))
                elif data.get("sgp41_voc", None) != None:
                    disp.showSensorValues(data.get("scd4x_co2", None), None, None, data.get("sgp41_voc", None), data.get("ltr390_lux", None))
                else:
                    disp.showSensorValues(data.get("scd4x_co2", None), None, None, None, data.get("ltr390_lux", None))
        if (time_old + log_interval) > time_new:
            alarm.light_sleep_until_alarms(time_alarm)
        else:
            time_old = time_new
            data = sensor.read_sensor()
            # TODO -> get wrong values with ESP32S2 ADC on CP
            # if vbat_adc: # Get Battery Voltage
            #     vbat = vbat_adc.value / 65535 * vbat_adc.reference_voltage
            # data["vbat"] = vbat
            if button1_pressed:
                data["button1"] = "pressed"
            elif button1_long_press:
                data["button1"] = "long_press"
            if button2_pressed:
                data["button2"] = "pressed"
            elif button2_long_press:
                data["button2"] = "long_press"
            button1_pressed = False
            button1_long_press = False
            button2_pressed = False
            button2_long_press = False
            data["unix_time"] = int(time.time())
            log.debug("Sensor Values: %s\n", json.dumps(data))
            if enable_csv:
                if not csv.write_data(data):
                    log.error("could not write csv file\n")
            if wifi.radio.ap_info:
                if tb_enable:
                    try:
                        ret = tb.send_telemetry(data)
                    except OSError as e:
                        tb_error_counter = tb_error_counter + 1
                        log.error("tb.send_telemetry OSError: %s\n", e)
                        traceback.print_exception(None, e, e.__traceback__)
                    except RuntimeError as e:
                        tb_error_counter = tb_error_counter + 1
                        log.error("tb.send_telemetry RuntimeError: %s\n", e)
                        traceback.print_exception(None, e, e.__traceback__)
                    else:
                        tb_error_counter = 0
                if mqtt_enable:
                    try:
                        mqtt_client.publish(full_topic, json.dumps(data))
                        mqtt_client.loop()
                    except OSError as e:
                        mqtt_error_counter = mqtt_error_counter + 1
                        log.error("mqtt_client.publish OSError: %s\n", e)
                        traceback.print_exception(None, e, e.__traceback__)
                    except RuntimeError as e:
                        mqtt_error_counter = mqtt_error_counter + 1
                        log.error("mqtt_client.publish RuntimeError: %s\n", e)
                        traceback.print_exception(None, e, e.__traceback__)
                    else:
                        mqtt_error_counter = 0
                if nr_enable:
                    try:
                        ret = nr.send_telemetry(data, full_topic, qos=1)
                    except OSError as e:
                        nr_error_counter = nr_error_counter + 1
                        log.error("nr.send_telemetry OSError: %s\n", e)
                        traceback.print_exception(None, e, e.__traceback__)
                    except RuntimeError as e:
                        nr_error_counter = nr_error_counter + 1
                        log.error("nr.send_telemetry RuntimeError: %s\n", e)
                        traceback.print_exception(None, e, e.__traceback__)
                    else:
                        nr_error_counter = 0
                if (
                    (tb_error_counter > max_errors)
                    or (mqtt_error_counter > max_errors)
                    or (nr_error_counter > max_errors)
                ):
                    log.error(
                        "Cloud Error. TB-Erros: %i, MQTT-Errors: %i, NR-Errors: %i\n",
                        tb_error_counter,
                        mqtt_error_counter,
                        max_errors,
                    )
                    time.sleep(10)
                    microcontroller.reset()
            else:  # wifi connection lost
                if enable_wdt:
                    wdt.feed()
                if enable_wifi:
                    log.warning("Wifi disconnected. Try to reconnect\n")
                try:
                    if enable_wifi:
                        ret = WifiManager.setup_network()
                except OSError as e:
                    log.error("OSError wifi: %s\n", e)
                    traceback.print_exception(None, e, e.__traceback__)
                    time.sleep(10)
                    microcontroller.reset()
                except RuntimeError as e:
                    log.error("RuntimeError wifi: %s\n", e)
                    traceback.print_exception(None, e, e.__traceback__)
                    time.sleep(10)
                    microcontroller.reset()
                if enable_wifi:
                    if ret:
                        log.debug("Wifi Connected to: %s\n", WifiManager.ssid)
                    else:
                        log.error("Wifi Error! No connection\n")
                        time.sleep(30)
                        microcontroller.reset()
except watchdog.WatchDogTimeout as e:
    log.error("Watchdog expired\n")
    traceback.print_exception(None, e, e.__traceback__)
    time.sleep(10)
    microcontroller.reset()
except Exception as e:
    log.error("Global Error: %s\n", e)
    traceback.print_exception(None, e, e.__traceback__)
    time.sleep(20)
    microcontroller.reset()
