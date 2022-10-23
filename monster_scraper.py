import json
import os
import re
import tempfile
from functools import reduce
from time import time
from zipfile import ZipFile

from PIL import Image

from selenium.webdriver.common.by import By
import selenium.common.exceptions as exceptions

import undetected_chromedriver as webdriver

SIZES = {"T": "tiny", "S": "small", "M": "medium", "L": "large", "H": "huge", "G": "gargantuan"}
ALIGNMENT = {"A": "any", "U": "unaligned", "C": "chaotic", "N": "neutral", "L": "lawful", "E": "evil", "G": "good"}


class ChromeWithPrefs(webdriver.Chrome):
    def __init__(self, *args, options=None, **kwargs):
        if options:
            self._handle_prefs(options)

        super().__init__(*args, options=options, **kwargs)

        self.keep_user_data_dir = False

    @staticmethod
    def _handle_prefs(options):
        if prefs := options.experimental_options.get("prefs"):
            def undot_key(key, value):
                if "." in key:
                    key, rest = key.split(".", 1)
                    value = undot_key(rest, value)
                return {key: value}

            undot_prefs = reduce(
                lambda d1, d2: {**d1, **d2},
                (undot_key(key, value) for key, value in prefs.items()),
            )

            user_data_dir = os.path.normpath(tempfile.mkdtemp())
            options.add_argument(f"--user-data-dir={user_data_dir}")

            default_dir = os.path.join(user_data_dir, "Default")
            os.mkdir(default_dir)

            prefs_file = os.path.join(default_dir, "Preferences")
            with open(prefs_file, encoding="latin1", mode="w") as f:
                json.dump(undot_prefs, f)

            # pylint: disable=protected-access
            del options._experimental_options["prefs"]


def cache_monsters(stats_file, statblocks_directory):
    if not stats_file and not statblocks_directory:
        return

    statblock_files = []

    def save(stat_dict):
        if stats_file:
            if not os.path.exists(stats_file):
                with open(stats_file, "x"):
                    pass

            with open(stats_file, "w") as f:
                json.dump({key: stat_dict[key] for key in sorted(stat_dict)}, f)

        if statblocks_directory:
            with ZipFile(os.path.join(statblocks_directory, "statblocks.zip"), "w") as zipfile:
                for file in statblock_files:
                    zipfile.write(file)

        driver.close()

    if statblocks_directory and os.path.exists(os.path.join(statblocks_directory, "statblocks.zip")):
        with ZipFile(os.path.join(statblocks_directory, "statblocks.zip")) as zipfile:
            statblock_files = zipfile.namelist()
            zipfile.extractall(statblocks_directory)

    prefs = {
        "download.default_directory": statblocks_directory,
        "profile.default_content_setting_values.automatic_downloads": 1
    }
    options = webdriver.ChromeOptions()
    options.add_experimental_option("prefs", prefs)
    options.add_argument("--window-position=99999999,9999999")
    options.add_argument("--window-size=1,1")
    options.add_argument("-WindowStyle Minimized")
    options.add_argument("-passthru")

    driver = ChromeWithPrefs(options=options)
    driver.get("https://5e.tools/bestiary.html")

    with open("monster_scraper_script.js") as f:
        script = f.read()

    start = time()
    while len(driver.find_elements(by=By.CLASS_NAME, value="stats-name")) == 0:
        if time() - start > 10:  # try again after 10 seconds
            start = time()
            driver.refresh()

    for e in driver.find_elements(by=By.CLASS_NAME, value="fltr__mini-pill--default-desel"):
        e.click()

    if stats_file:
        if os.path.exists(stats_file):
            with open(stats_file) as f:
                all_stats = json.load(f)
        else:
            all_stats = {}

    driver.minimize_window()
    try:
        for e in driver.find_elements(by=By.CLASS_NAME, value="lst__row"):
            while True:
                try:
                    e.click()
                except exceptions.ElementClickInterceptedException:
                    continue

                break

            while e.find_elements(by=By.CLASS_NAME, value="bold")[0].get_attribute("innerText") != \
                    driver.find_elements(by=By.CLASS_NAME, value="stats-name")[0].get_attribute("innerText"):
                pass

            source = driver.find_elements(by=By.CLASS_NAME, value="stats-source-abbreviation")[0].get_attribute(
                "innerText")
            name = driver.find_elements(by=By.CLASS_NAME, value='stats-name')[0].get_attribute(
                'innerText').lower().replace(' ', '_').replace('"', "'").replace(".", "") + '-' + source

            print("scraping " + name)

            if statblocks_directory:
                img_path = os.path.join(statblocks_directory, f"{name}.png")
                if os.path.exists(img_path):
                    continue
            if not statblocks_directory and stats_file and name in all_stats:
                continue

            if stats_file:
                for b in driver.find_elements(by=By.CLASS_NAME, value="ui-tab__btn-tab-head"):
                    if "Popout Window" in b.get_attribute("title"):
                        b.click()

                driver.find_elements(by=By.CLASS_NAME, value="hwin__top-border-icon--text")[0].click()
                stats = json.loads(driver.find_elements(by=By.CLASS_NAME, value="mb-1")[-1].get_attribute("innerText"))

                alignment = None if "alignment" not in stats else (
                    (stats["alignment"][0]["alignment"] if "alignment" in stats["alignment"][0] else None) if type(
                        stats["alignment"][0]) == dict else stats["alignment"])
                speeds = stats["speed"] if type(stats["speed"]) == dict else {"walk": stats["speed"]}
                if "canHover" in speeds:
                    del speeds["canHover"]

                all_stats[name] = {
                    "name": stats["name"],
                    "cr": stats["cr"] if "cr" in stats else "—",
                    "size": SIZES[stats["size"][0]],
                    "alignment": "—" if alignment is None else (
                        "any evil" if "NX" in alignment else f"{ALIGNMENT[alignment[0]]}{' '+ALIGNMENT[alignment[1]] if len(alignment) > 1 else ''}"
                    ),
                    "type": stats["type"]["type"] if type(stats["type"]) == dict else stats["type"],
                    "subtypes": stats["type"]["tags"] if type(stats["type"]) == dict and "tags" in stats["type"] else [],
                    "speeds": speeds,
                    "hp": stats["hp"]["average"] if "average" in stats["hp"] else "—"
                }

                remove = driver.find_elements(by=By.CLASS_NAME, value="glyphicon-remove")
                remove[3].click()
                remove[2].click()

            if statblocks_directory:
                driver.set_window_size(min(driver.find_element(value="pagecontent").size['height']/765 * 513, 1002), 1)

                while True:
                    try:
                        driver.execute_script(script.replace("|NAME|", name))
                    except exceptions.JavascriptException:
                        while True:
                            try:
                                exec(input(">>> "))
                            except Exception as e:
                                print(e)
                                pass

                    statblock_files.append(img_path)

                    while not os.path.exists(img_path):
                        pass

                    img = None
                    while True:
                        try:
                            img = Image.open(img_path)
                        except PermissionError:
                            continue

                        break

                    pagecontent = driver.find_element(value="pagecontent")

                    if img.width != pagecontent.size["width"] or img.height != pagecontent.size["height"]:
                        print(
                            f"{name}: incorrect size! element: ({e.size['width']},{e.size['height']})\
                            image: ({img.width}, {img.height})"
                        )
                        img.close()
                        os.remove(img_path)
                        continue
                    img.close()

                    break

    except BaseException as e:
        save(all_stats)
        raise e

    save(all_stats)
