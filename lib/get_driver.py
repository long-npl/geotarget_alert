import os
import sys
import json
import pickle
import shutil
import requests
from glob import glob
from time import sleep
from selenium import webdriver
from datetime import datetime, timedelta
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager
from urllib3.exceptions import MaxRetryError


class WebDriver:
    def __init__(self, download_dir=None, proxy=None, timeout=30, dl_timeout=300):
        self.download_dir = download_dir
        self.proxy = proxy
        self.browser_timeout = timeout
        self.dl_timeout = dl_timeout
        self.driver = None

    def get_chrome(self):
        chrome_options = webdriver.ChromeOptions()

        if self.download_dir is not None:
            prefs = {"download.default_directory": os.path.abspath(
                self.download_dir)}
            chrome_options.add_experimental_option("prefs", prefs)

        chrome_options.add_argument('--disable-infobars')
        chrome_options.add_argument('--start-maximized')
        chrome_options.add_argument('--log-level=3')

        if self.proxy:
            print("add proxy")
            chrome_options.add_argument(f'--proxy-server=http://{self.proxy}')

        chrome_options.add_experimental_option("excludeSwitches",
                                               [
                                                   # "ignore-certificate-errors",
                                                   "safebrowsing-disable-download-protection",
                                                   "safebrowsing-disable-auto-update",
                                                   # "disable-client-side-phishing-detection"
                                               ]
                                               )

        chrome_options.add_argument("--incognito")
        chromeLocalStatePrefs = {'browser.enabled_labs_experiments': [
            'download-bubble@2', 'download-bubble-v2@2']}
        chrome_options.add_experimental_option(
            'localState', chromeLocalStatePrefs)

        # print("Chrome path: {}".format(self.exe_path))
        try:
            # self.driver = webdriver.Chrome(ChromeDriverManager().install(), options=chrome_options)
            self.driver = webdriver.Chrome(service=ChromeService(), options=chrome_options)
        except:
            self.driver = webdriver.Chrome(executable_path=os.path.join(
                os.getcwd(), "00_setting", "chromedriver.exe"), options=chrome_options)

        # run by chromeDriverManager
        return self.driver

    def get_defaultProfile_chrome(self):
        chrome_options = webdriver.ChromeOptions()

        if self.download_dir is not None:
            prefs = {"download.default_directory": os.path.abspath(
                self.download_dir)}
            chrome_options.add_experimental_option("prefs", prefs)

        # chrome_options.add_argument('--disable-infobars')
        # chrome_options.add_argument('--start-maximized')
        # chrome_options.add_argument('--log-level=3')

        chrome_options.add_argument(
            r'user-data-dir=C:\Users\DT0083\AppData\Local\Google\Chrome\User Data')
        chrome_options.add_argument("profile-directory=Default")

        if self.proxy:
            print("add proxy")
            chrome_options.add_argument(f'--proxy-server=http://{self.proxy}')

        # chrome_options.add_experimental_option("excludeSwitches",
        #                                        [
        #                                            # "ignore-certificate-errors",
        #                                            "safebrowsing-disable-download-protection",
        #                                            "safebrowsing-disable-auto-update",
        #                                            # "disable-client-side-phishing-detection"
        #                                        ]
        #                                        )

        # chrome_options.add_argument("--incognito")
        # print("Chrome path: {}".format(self.exe_path))

        self.driver = webdriver.Chrome(
            ChromeDriverManager().install(), options=chrome_options)

    def get_firefox(self):

        # run by chromeDriverManager
        self.driver = webdriver.Firefox(
            executable_path=GeckoDriverManager().install())

    def get(self, the_url):
        # if have not has drive yet
        if not self.driver:
            self.get_chrome()
        try:
            self.driver.get(the_url)
        except MaxRetryError:
            self.get_chrome()
            self.driver.get(the_url)

    def save_cookie(self, path='myCookie.pickle'):
        with open(path, 'wb') as filehandler:
            pickle.dump(self.driver.get_cookies(), filehandler)

    def load_cookie(self, path='myCookie.pickle'):
        with open(path, 'rb') as cookiesfile:
            cookies = pickle.load(cookiesfile)
            for cookie in cookies:
                try:
                    self.driver.add_cookie(cookie)
                except:
                    print(f'can not add cookie: {cookie}')

    def check_download(self):
        sleep(2)
        downloading_files = glob(os.path.join(self.download_dir, "*crdownload*")) + glob(
            os.path.join(self.download_dir, "*.tmp*"))
        count = 0
        while downloading_files:
            print("Detected downloading files: ", len(downloading_files))
            sleep(1)
            if count <= self.dl_timeout:
                count += 1
                downloading_files = glob(os.path.join(self.download_dir, "*crdownload*")) + glob(
                    os.path.join(self.download_dir, "*.tmp*"))
            else:
                with open(os.path.join(os.getcwd(), 'download_error_log.log')) as writer:
                    writer.write(
                        "[{}] Download Timeout: Please try again!".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                self.quit()

    def click_element_by_xpath(self, xpath: str, timeout=None):
        if timeout is None:
            timeout = self.browser_timeout
        return WebDriverWait(self.driver, timeout).until(
            EC.element_to_be_clickable((By.XPATH, xpath))).click()

    def safe_click_element_by_xpath(self, xpath: str, timeout=None):
        if len(self.get_elements_by_xpath(xpath, timeout)) == 1:
            self.click_element_by_xpath(xpath)

    def send_keys_to_element_by_xpath(self, xpath, keys_str):
        WebDriverWait(self.driver, self.browser_timeout).until(
            EC.element_to_be_clickable((By.XPATH, xpath))).clear()
        WebDriverWait(self.driver, self.browser_timeout).until(
            EC.element_to_be_clickable((By.XPATH, xpath))).send_keys(keys_str)

    def safe_send_keys_element_by_xpath(self, xpath: str, keys_strs):
        if len(self.get_elements_by_xpath(xpath)) == 1:
            self.send_keys_to_element_by_xpath(xpath, keys_strs)

    def wait_element_by_xpath(self, xpath: str):
        return WebDriverWait(self.driver, self.browser_timeout).until(
            EC.visibility_of_element_located((By.XPATH, xpath)))

    def get_element_by_xpath(self, xpath: str):
        return WebDriverWait(self.driver, self.browser_timeout).until(
            EC.presence_of_element_located((By.XPATH, xpath)))

    def get_elements_by_xpath(self, xpath: str, timeout=None):
        if timeout is None:
            timeout = self.browser_timeout
        return WebDriverWait(self.driver, timeout).until(
            EC.presence_of_all_elements_located((By.XPATH, xpath)))

    def quit(self):
        if self.driver:
            self.driver.quit()
        self.driver = None

    def restart(self):
        self.driver.quit()
        self.driver = self.get_chrome()

    def highlight_by_xpath(self, xpath: str):
        """Highlights (blinks) a Selenium Webdriver element"""

        element = WebDriverWait(self.driver, self.browser_timeout).until(
            EC.visibility_of_element_located((By.XPATH, xpath)))

        browser = element._parent

        def appy_style(s):
            browser.execute_script(
                "arguments[0].setAttribute('style', arguments[1]);", element, s)

        original_style = element.get_attribute('style')
        appy_style("background: yellow; border: 2px solid red;")
        sleep(1)
        appy_style(original_style)
        sleep(0.3)

    def highlight_element(self, element):
        """Highlights (blinks) a Selenium Webdriver element"""

        browser = element._parent

        def appy_style(s):
            browser.execute_script(
                "arguments[0].setAttribute('style', arguments[1]);", element, s)

        original_style = element.get_attribute('style')
        appy_style("background: yellow; border: 2px solid red;")
        sleep(1)
        appy_style(original_style)
        sleep(0.3)