from bs4 import BeautifulSoup
from collections import namedtuple
from urllib.parse import urljoin
from queue import Queue
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver import Chrome
from threading import Thread
from wordcloud import WordCloud

import jieba
import re
import matplotlib.pyplot as plt


Thumbnail = namedtuple('DcardPostThumbnail', ['title', 'url'])
Post = namedtuple('DcardPost', ['title', 'content', 'replies'])

POSTS_NUMBER = 1
URL_BASE = 'https://www.dcard.tw/f'


def get_thumbnails(driver):
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    main_div = soup.select_one('#__next '
                               '> div.bvk29r-0.jhIZYh '
                               '> div.bvk29r-2.glwZhP')
    return main_div.find_all('a', class_='tgn9uw-3')


def scroll_down(driver, times=3, to_end=False):
    if to_end:
        driver.execute_script(
                "window.scrollTo(0,document.body.scrollHeight)")

    for _ in range(times):
        driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.PAGE_DOWN)


def parse_thumbnail(element):
    return Thumbnail(element.text, element['href'])


def get_posts(url_queue, out_queue, index):
    # get post in another thread
    print(f'PostGetter {index}: Start')
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    thr_driver = Chrome("chromedriver", options=chrome_options)
#    thr_driver = Chrome('chromedriver')

    print(f'PostGetter {index}: Begin looping.')
    while not url_queue.empty():
        url = url_queue.get()
        print(f'PostGetter {index}: Fetch data from {url}')
        thr_driver.get(urljoin(URL_BASE, url))

        soup = BeautifulSoup(thr_driver.page_source, 'html.parser')
        title = soup.find('h1').text
        print(f'PostGetter {index}: Title = {title}')
        contents = soup.find_all('div', class_='phqjxq-0')
        rep_meta = soup.find_all(
                'div', class_='sc-3l0xho-1 dPtjOZ')[-1].text
        reply_number = int(re.sub('\D', '', rep_meta))
        contents = []
        flag = [1, 0, 0, 0, 0]  # stop condition = all the same number
        while not (flag[0] == flag[1] and flag[1] == flag[2] and
                   flag[2] == flag[3] and flag[3] == flag[4]):
            scroll_down(thr_driver)
            soup = BeautifulSoup(thr_driver.page_source, 'html.parser')
            this_time = soup.find_all('div', class_='phqjxq-0')
            contents += this_time
            contents = list(set(contents))
            flag.insert(0, len(contents))
            flag.pop()
            print(flag)

        print(f'PostGetter {index}: Close {url}')

        content = contents[0]
        replies = contents[1:]
        out_queue.put(Post(title=title, content=content, replies=replies))

        url_queue.task_done()
        print(f'PostGetter {index}: Job done {url}')

    print(f'PostGetter {index}: All jobs done.')
    thr_driver.close()


def main():
    # Get post list
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    driver = Chrome("chromedriver", options=chrome_options)
#    driver = Chrome('chromedriver')
    driver.get(URL_BASE)

    # Get enough post links
    thumbnails = []
    while len(thumbnails) <= POSTS_NUMBER:
        scroll_down(driver)
        thumbnails += list(map(parse_thumbnail, get_thumbnails(driver)))
        thumbnails = list(set(thumbnails))

    driver.close()

    # Insert URLs into a queue for multithreading
    url_queue = Queue()
#    for thumbnail in thumbnails:
#        url_queue.put(urljoin(URL_BASE, thumbnail.url))
    url_queue.put(urljoin(URL_BASE, thumbnails[0].url))

    # Get posts
    post_queue = Queue()
    threads = [Thread(target=get_posts, args=(url_queue, post_queue, i))
               for i in range(1)]
    for thr in threads:
        thr.start()

    for thr in threads:
        thr.join()

    # Concatnates all words in all posts
    posts = []
    while not post_queue.empty():
        posts.append(post_queue.get())
        post_queue.task_done()

    text = ''
    for i in posts:
        text += i.title + '\n'
        text += i.content.text + '\n\n'
        replies = [r.text for r in i.replies]
        text += '\n\n'.join(replies) + '\n\n'

    # Jieba Chinese word-cutting
    jieba.set_dictionary('dict.txt')
    stopwords = ['。', '，', '、', 'ㄧ', '”', ' ', '\n', '?',
                 '了', '!', '的', '“', '(', ')', '⋯', '.',
                 '+', '~', ' ', '：', '？', '！', '我']
    for w in stopwords:
        text = text.replace(w, '')
    words = ' '.join(jieba.cut(text, cut_all=True))

    # WordCloud
    font_path = '/usr/share/fonts/noto-cjk/NotoSansCJK-Black.ttc'
    wordcloud = WordCloud(max_words=1000, background_color="white",
    font_path=font_path).generate(words)

    plt.figure()
    plt.imshow(wordcloud, interpolation="bilinear")
    plt.axis("off")
    plt.show()


if __name__ == '__main__':
    main()
