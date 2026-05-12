import logging
import logging.config
from decouple import config
import time
import traceback
import datetime
from functools import wraps


logging.config.fileConfig(str(config('LOG_SETTING_CONF')))


def decorator_calculateTime(func):
    '''caculate processing time of function
    '''
    # added arguments inside the inner1,
    # if function takes any arguments,
    # can be added like this.
    def inner(*args, **kwargs):

        # storing time before function execution
        begin = time.time()

        output = func(*args, **kwargs)

        # storing time after function execution
        end = time.time()
        logging.info(f"@>>> {func.__qualname__}>> run in : {end - begin:.2f}s")
        return output

    return inner


def decorator_retryFunction(func):
    '''retry function, if reach max retry then raise error
    '''
    def inner(*args, **kwargs):
        is_done = False
        int_retry = 0
        int_max_retry = 3

        while not is_done:
            int_retry += 1
            try:
                output = func(*args, **kwargs)
                is_done = True
                return output
            except Exception as e:
                print('Error at retry no.{} -- '.format(str(int_retry))+str(e))

            if int_retry == int_max_retry:
                break

        if int_retry == int_max_retry or not is_done:
            raise ValueError(f'retry fail -- total retry: {int_max_retry}')

    return inner


def decorator_catchError(argument):
    '''try to run function, if error return passed parameter as error code
    '''
    def decorator(function):

        def wrapper(*args, **kwargs):
            try:
                result = function(*args, **kwargs)
                return result

            except Exception as e:
                print(
                    f'error code: {argument} -- func: {function.__name__}')
                # traceback.print_exc()

                with open("__root.log", 'a') as f:
                    f.write('\n{}{}:{}{} '.format(r'#',
                                                  datetime.datetime.now().strftime('%y%m%d %H:%M:%S'), 'CRITICAL ERROR', r'\\'))
                    traceback.print_exc(file=f)

                # raise e
        return wrapper

    return decorator


def decorator_debug(func):
    '''decorator for debugging passed function'''

    @wraps(func)
    def wrapper(*args, **kwargs):
        logging.info(f"@>>> {func.__qualname__}>> Start!")
        return func(*args, **kwargs)
    return wrapper


def decorator_debug_class(cls):
    '''class decorator make use of debug decorator
       to debug class methods '''

    # check in class dictionary for any callable(method)
    # if exist, replace it with debugged version
    for key, val in vars(cls).items():
        if callable(val):
            setattr(cls, key, decorator_debug(val))
    return cls