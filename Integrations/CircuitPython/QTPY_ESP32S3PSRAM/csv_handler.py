import board
import time
import storage
import os


class csv_handler:
    def __init__(self, uid: str, dict_keys: list)  -> None:
        self._uid = uid
        self._dict_keys = dict_keys
        self._csv_header_str =  ('time,'+','.join(self._dict_keys))
        s = os.statvfs("/")
        self.total_size = (s[2] * s[1]) / 1024

    def write_data(self, sensor_data: dict) -> bool:
        try:
            storage.remount("/", False)
            # check free flash size
            s = os.statvfs("/")
            free_size = (s[4] * s[1]) / 1024
            usage_percent = (free_size/self.total_size)*100
            if usage_percent < 10: # smaller 10%
                print("flash full: %f%%\n" % usage_percent)
                return False
            date = time.localtime()
            file_str = ("/%s_%d%02d%02d.csv" % (self._uid,date.tm_year,date.tm_mon, date.tm_mday))
            try:
                with open(file_str, "r") as fp: # File exist
                    pass
            except:
                with open(file_str, "w") as fp: # new file
                    fp.write('%s\n' % self._csv_header_str)
                    fp.flush()
            with open(file_str, "a") as fp:
                data_str = ("%02d:%02d:%02d" % (date.tm_hour,date.tm_min, date.tm_sec))
                for key in self._dict_keys:
                    data_str = (data_str + ',{}'.format(sensor_data.get(key, "--")))
                data_str = (data_str + "\n")
                fp.write(data_str)
                fp.flush()
            return True
        except Exception as e:
            return False