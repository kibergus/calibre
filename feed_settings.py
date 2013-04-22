import re
from calibre.web.feeds.multy_feed import refactor_xkcd_image, substitute_latex
import copy

class FeedFetchSettings(object):
    def fetch(self, recipe, article, url, *args):
        return recipe.fetch_embedded_article(article, *args)

    def print_version_url(self, url):
        return url

    def postprocess_html(self, soup, first_fetch):
        return soup

class FeedXKCDSettings(FeedFetchSettings):
    def fetch(self, recipe, article, url, *args):
        try:
            article.summary = refactor_xkcd_image(article.summary)
        except Exception, e:
            pass
        return recipe.fetch_embedded_article(article, *args)

class FeedWhatIfSettings(FeedFetchSettings):
    def fetch(self, recipe, article, url, *args):
        try:
            r = re.compile(r'<img[^>]*class="illustration"[^>]*>', re.DOTALL)
            article.summary = r.sub(refactor_xkcd_image, article.summary)

            r = re.compile(r'\\[\[\(](.*?[^\\](\\\\)*)\\[\]\)]', re.DOTALL)
            article.summary = r.sub(substitute_latex, article.summary)
        except Exception, e:
            traceback.print_exc()
        return recipe.fetch_embedded_article(article, *args)

class FeedHabrahabrSettings(FeedFetchSettings):
    def fetch(self, recipe, article, url, *args):
        return recipe.fetch_article(url, *args)

    def print_version_url(self, url):
        return "http://m." + url[len("http://"):]

    def postprocess_html(self, soup, first_fetch):
        soup.find("div", attrs={"class" : "tm"}).extract()
        soup.find("div", attrs={"class" : "ft"}).extract()
        soup.find("div", attrs={"class" : "bm"}).extract()
        soup.find("img", attrs={"style" : "width:1px; height: 1px"}).extract()
        soup.body["style"] = "font-size:1em;"
        return soup

class FeedKommersantSettings(FeedFetchSettings):
    def fetch(self, recipe, article, url, *args):
        return recipe.fetch_article(url, *args)

    def print_version_url(self, url):
        id_part =  url.split("/")[-2].replace("0C", "/").split("/")[-1]
        id = id_part.replace("A", "")
        return "http://www.kommersant.ru/pda/news.html?id={0}".format(id)

    def postprocess_html(self, soup, first_fetch):
        for tag in soup.findAll("td"):
            if tag.get("class", None) == "issues":
                content = tag
                break
        else:
            content = soup.body

        more_link = content.find("a", attrs={"class" : "more"})
        if more_link is not None:
            more_link.parent.extract()
        content.name = "body"

        for i in reversed(range(len(content.contents))):
            child = content.contents[i]
            if hasattr(child, "name") and child.name == "br" or str(child).strip() == "":
                child.extract()
            else:
                break

        soup.body.replaceWith(content)
        return soup
