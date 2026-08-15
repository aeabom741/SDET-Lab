import logging
import allure


LOG_LEVEL = logging.DEBUG
FORMAT = '[AUTOMATION_SDK] %(asctime)s %(levelname)s %(message)s'


class HandlLog:
    _first_log_of_test = True

    def __init__(self) -> None:
        self.__logger = logging.getLogger()
        self.__logger.setLevel(LOG_LEVEL)

    @staticmethod
    def __init__stream_handler():
        return logging.StreamHandler()

    @classmethod
    def reset_first_log(cls):
        cls._first_log_of_test = True

    def set_add_handler(self, console_log):
        self.__logger.addHandler(console_log)

    @staticmethod
    def set_formatter(console_log):
        formatter = logging.Formatter(FORMAT)
        console_log.setFormatter(formatter)

    def __console(self, level, message):
        console_log = self.__init__stream_handler()
        self.set_add_handler(console_log)
        self.set_formatter(console_log)

        if HandlLog._first_log_of_test:
            print()
            HandlLog._first_log_of_test = False

        if level == 'info':
            self.__logger.info(message)
        elif level == 'debug':
            self.__logger.debug(message)
        elif level == 'warning':
            self.__logger.warning(message)
        elif level == 'error':
            self.__logger.error(message)
        elif level == 'critical':
            self.__logger.critical(message)

        self.__logger.removeHandler(console_log)

    def debug(self, message):
        self.__console('debug', message)

    def info(self, message):
        self.__console('info', message)

    def warning(self, message):
        self.__console('warning', message)

    def error(self, message):
        self.__console('error', message)

    def critical(self, message):
        self.__console('critical', message)

    def __set_up(self, full_log):
        with allure.step(f'{full_log}'): pass

    def __handle_log(self, full_log) -> None:
        self.__set_up(full_log)
        self.debug(full_log)

    def handle_log(self, full_log: str) -> None:
        self.__handle_log(full_log)