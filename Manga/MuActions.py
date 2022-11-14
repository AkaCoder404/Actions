import requests
import os
import pickle
from bs4 import BeautifulSoup

# environment variables (using environment secrets for github actions)
app_token = os.environ.get("APP_TOKEN")
user_key = os.environ.get("USER_KEY")
username = os.environ.get("MU_USERNAME")
password = os.environ.get("MU_PASSWORD")
device = "Manga Updates"

# send pushover message
def pushover_message(app_token, user_key, device, message):
    r = requests.post(
        "https://api.pushover.net/1/messages.json",
        data={
            'title': device,
            'token': app_token,
            'user': user_key,
            'message': message
            },
        # files={"attachment":open("PATH_TO_IMAGE","rb") // for images
        )

# bot to crawl mangaupdates
class MangaUpdates:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/"
        })
        self.cookies_path = "data/cookies.txt"
        self.login_url = "https://www.mangaupdates.com/login.html"
        self.login_action = "?act=login&username={}&password={}".format(self.username, self.password)

        self.my_list = "https://www.mangaupdates.com/mylist.html"
        self.rss_feed = "https://www.mangaupdates.com/rss.php"
        self.session.cookies = self.load_cookies()
    
    def load_cookies(self) -> requests.cookies.RequestsCookieJar:
        cookies = None
        if os.path.exists(self.cookies_path):
            try:
                with open(self.cookies_path, "rb") as f:
                    cookies = pickle.load(f)
                print(f"cookies loaded from file {self.cookies_path}")
                return cookies
            except Exception as e:
                print(f"reading cookies error: {e}")
        else:
            print(f"cookie file does not exist: {self.cookies_path}")
        if cookies:
            return cookies
        else:
            return requests.cookies.RequestsCookieJar()

    # login to mangaupdates
    def login(self) -> bool:
        try_time = 1
        while True:
            response = self.session.post(f"{self.login_url}{self.login_action}")
            if f"Welcome back, {self.username}" in response.text:
                print(f"login successful")
                os.makedirs(os.path.dirname(self.cookies_path), 0o755, True)
                with open(self.cookies_path, "wb") as f:
                    pickle.dump(self.session.cookies, f)
                print(f"cookies wrote to file")
                return True
            try_time -= 1
            if try_time > 0:
                print(f"log in error, try again ({try_time} left)")
            else:
                print("flog in error after 10 tries")
                return False
    
    # get mylist
    def scrape(self, url):
        try:
            page = self.session.get(url)
            soup = BeautifulSoup(page.text, "html.parser")
            return soup
        except Exception as e:
            print(e)

    # parse mylist
    def parse(self, soup):
        main_content = soup.find("div", {"id": "main_content"})
        table_list = main_content.find("div", {"id": "list_table"})
        t_list = table_list.find_all("div", recursive=False)
        print(f"you have {len(t_list)} mangas in your list")
        manga_list = []
        for row in t_list:
            cols = row.find_all("div", recursive=False)

            # col[0] - checkbox
            # col[1] - manga description
            # col[2] - status
            # col[3] - rating
            # col[4] - average

            manga_link = cols[1].find("a")["href"]
            manga_title = str(cols[1].find("a").text)
            manga_list.append({"title": manga_title, "link": manga_link})
    
            # print(f"{manga_title} - {manga_link}")
        
        return manga_list
    
    # parse rss feed
    def rss_list(self, url):
        # scrape
        feed = requests.get(url)
        soup = BeautifulSoup(feed.text, "xml")
        
        # parse
        items = soup.find_all("item")
        manga_list = []
        for item in items:
            title = item.title.text
            description = [] if item.description.text is None else item.description.text.split("<br />")
            # description = item.description
            date = description[0]
        
            # print(description)
            link = ""
            if item.link:
                link = item.link.text
            
            scan = title[1:title.find("]")]
            chapter = title[title.rfind("c"):].split("-")[0].split(" ")[0]
            title = title[title.find("]")+2:title.rfind("c")-1]
            tail = ""
            if len(title) > 75:
                tail = "..."
            title = '{:<15}'.format(title[:75]) + tail
            # print(f"{date} | {chapter} \t| {title} | {link}")
            manga_list.append({"title": title, "link": link, "chapter": chapter, "scan": scan, "date": date})
        
        print("rss feed of {} mangas".format(len(items)))
        return manga_list

    def update(self): 
        # 1. get the list of mangas in mylist
        # 2. get the list of mangas in the rss feeds
        # 3. compare the two lists and return new ones
        
        # see if can access the mylist page, otherwise, login
        response = self.session.get(self.my_list)
        if "Welcome to Your Reading List" not in response.text:
            print("not logged in, trying to log in")
            if not self.login():
                print("login failed")
                return "login failed"
        
        soup = self.scrape(self.my_list)
        my_manga_list = self.parse(soup)
        update_list = self.rss_list(self.rss_feed)
        
        updates = []
        for my_manga in my_manga_list:
            for update in update_list:
                if my_manga["link"] == update["link"]:
                    updates.append(update)
                    # print(f"{my_manga['title']} {update['link']} has new update {update['chapter']}")
                    break
        
        # construct message
        count = 1
        update_message = ""
        for u in updates:
            # print(f"[{count}] {u['title']} has new update {u['chapter']}")
            update_message += f"[{count}] {u['date']} {u['title']} {u['chapter']}" + "\n"
            count += 1

        return update_message

# run
bot = MangaUpdates(username, password)
message = bot.update()
message = "User: " + username + "\n" + message
if message != "":
    pushover_message(app_token=app_token, user_key=user_key, device=device, message=message)
else:
    print("no new updates")