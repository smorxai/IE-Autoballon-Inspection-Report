
import logging
import logging.handlers
import os
import platform
import shutil
import time
import threading
from datetime import datetime
from enum import Enum
from genericpath import exists
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler


class LoggingLevel(Enum):
    NOTSET = 0
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


"""
Custom log handler that creates a new log file every day and organizes logs
into folders by date and module name. It also creates a symbolic link to the latest log file.

Inherits:
    TimedRotatingFileHandler: Standard Python handler that rotates log files by time.

Parameters:
    log_file (str): Initial log file path.
    module_name (str): Name of the module generating logs.
    date (str): Current date string (format: DD-MM-YYYY).
    base_foler (str): Base folder path where logs should be stored.
"""
class DateWiseRotatingFileHandler(TimedRotatingFileHandler):
    def __init__(self, log_file=None, module_name="Global", date=None, base_foler=None):
        self._lock = threading.Lock()
        self._date = date
        self._baseFolder = base_foler
        self._moduleName = module_name
        super().__init__(filename=log_file, when='D', interval=1)


    """
    Check if the log file should roll over.

    Parameters:
        record (LogRecord): The log record being processed.

    Returns:
        int: 1 if the date changed (triggering a new log file), else None.
    """
    def shouldRollover(self, record):
        current_date = datetime.today().strftime("%d-%m-%Y")
        if current_date != self._date:
            self._date = current_date
            return 1


    """
    Perform the log file rollover. Creates a new directory structure (base_folder/date/module) and
    links the latest log file as `log.log` (for easy access).

    Parameters:
        Nil

    Returns:
        Nil
    """
    def doRollover(self):
        with self._lock:
            if self.stream:
                self.stream.close()
                self.stream = None

            current_time = int(time.time())
            time_tuple = time.localtime(current_time)
            log_suffix_file = self.rotation_filename(self.baseFilename + "." + time.strftime(self.suffix, time_tuple))

            # Remove the log file with suffix to avoid extra log files
            if os.path.exists(log_suffix_file):
                os.remove(log_suffix_file)

            time1 = datetime.now().strftime("%H.%M.%S")
            log_file_path = "{0}/{1}/{2}".format(self._baseFolder, self._date, self._moduleName)
            Path(log_file_path).mkdir(parents=True, exist_ok=True)
            log_file_name = "{0}.log".format(time1)
            self.baseFilename = log_file_path + "/" + log_file_name
            if not self.delay:
                self.stream = self._open()
                if platform.system() == "Linux":
                    link_file_command = 'cd {log_folder_path:}&& ln -sf {s:} {d:}'.format(log_folder_path = log_file_path, s=log_file_name, d="log.log")
                    os.system(link_file_command)
            self.mode = 'a'



"""
Application logger that creates date-wise rotating logs and automatically
manages old log folders (deleting the oldest after a retention period).

Inherits:
    logging.Logger: Python standard Logger class.

Parameters:
    name (str): Name of the logger (default: "Global").
    module_name (str): Name of the module generating logs.
    file (bool): Include filename in log format.
    func (bool): Include function name in log format.
    line (bool): Include line number in log format.
    level (LoggingLevel): Logging level (default: DEBUG).
    log_path (str): Base path for storing logs.
    backup_days (int): Number of days to keep old logs.
"""
class AppLogger(logging.Logger):
    def __init__(self, name="Global", module_name="Global", file=True, func=True, line=True, level=LoggingLevel.DEBUG, log_path = None, backup_days=30):
        super().__init__(name, level.value)
        formatter_string = "%(asctime)s [%(levelname)8s] "
        if module_name=="Global" or file==True:
            formatter_string = formatter_string + "%(filename)s:"
        if module_name=="Global" or func==True:
            formatter_string = formatter_string + "%(funcName)s:"
        if module_name=="Global" or line==True:
            formatter_string = formatter_string + "%(lineno)d"
        formatter_string = formatter_string + " %(message)s"
        formatter = logging.Formatter(formatter_string)
        date = datetime.today().strftime("%d-%m-%Y")
        time = datetime.now().strftime("%H.%M.%S")
        if ((log_path != None) and (os.path.exists(log_path))):
            log_path_folder = log_path + "/Logs"
            log_file_path = "{0}/{1}/{2}".format(log_path_folder, date, module_name)
        else:
            log_path_folder = "./Logs"
            log_file_path = "{0}/{1}/{2}".format(log_path_folder, date, module_name)
        Path(log_file_path).mkdir(parents=True, exist_ok=True)
        log_file_name = "{0}.log".format(time)
        log_file = log_file_path + "/" + log_file_name
        if platform.system() == "Linux":
            link_file_command = 'cd {log_folder_path:}/{date:}/{module:} && ln -sf {s:} {d:}'.format(log_folder_path = log_path_folder, date = date, module = module_name, s=log_file_name, d="log.log")
            os.system(link_file_command)
        # handler = logging.FileHandler(log_file)
        handler = DateWiseRotatingFileHandler(log_file=log_file, module_name=module_name, date=date, base_foler=log_path_folder)
        handler.setFormatter(formatter)
        self.addHandler(handler)

        # Delete Oldest Log Folders
        if exists(log_path_folder):
            folders_list = os.listdir(log_path_folder)
            folders_list = [os.path.join(log_path_folder, folder) for folder in folders_list]
            while len(folders_list) > backup_days:
                oldest_folder = min(folders_list , key=os.path.getctime)
                shutil.rmtree(os.path.abspath(oldest_folder))


"""
System logger that writes logs to the system's syslog (/dev/log).
Suitable for Linux environments where system logs are managed by journald or syslog.

Inherits:
    logging.Logger: Python standard Logger class.

Parameters:
    name (str): Logger name (default: "syslogger").
    file (bool): Include filename in log format.
    func (bool): Include function name in log format.
    line (bool): Include line number in log format.
    level (LoggingLevel): Logging level (default: DEBUG).
"""
class SysLogger(logging.Logger):
    def __init__(self, name="syslogger", file=True, func=True, line=True, level=LoggingLevel.DEBUG):
        super().__init__(name, level.value)
        formatter_string = "%(asctime)s [%(levelname)8s] "
        if file==True:
            formatter_string = formatter_string + "%(filename)s:"
        if func==True:
            formatter_string = formatter_string + "%(funcName)s:"
        if line==True:
            formatter_string = formatter_string + "%(lineno)d"
        formatter_string = formatter_string + " %(message)s"
        formatter = logging.Formatter(formatter_string)
        handler = logging.handlers.SysLogHandler(address = '/dev/log')
        handler.setFormatter(formatter)
        self.addHandler(handler)