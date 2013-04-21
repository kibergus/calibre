from calibre import unicode_path, __appname__
from calibre.web.feeds import feeds_from_index
from calibre.web.feeds.recipes import AutomaticNewsRecipe, BasicNewsRecipe
from calibre.web.fetch.simple import RecursiveFetcher
from calibre.utils.threadpool import WorkRequest, ThreadPool, NoResultsPending
from calibre.utils.filenames import ascii_filename

import subprocess
import traceback
import tempfile
import urlparse
import urllib2
import shutil
import time
import os
import re

from cStringIO import StringIO
from BeautifulSoup import BeautifulSoup
from PIL import Image

#======= helper functions ===========

# Image paths can't be changed during html postprocess. So this work is done with regexps
xkcd_title_re = re.compile(r'(<img.*title=")([^"]+)(".*>)')
def refactor_xkcd_image(tag):
    """ xkcd has every image titled with a funny phrase. Add these phrases below images. """
    if not isinstance(tag, basestring):
        tag = tag.group(0)
    m = xkcd_title_re.match(tag)
    result = '<center>%s%s<br /><i>%s</i></center>' % (m.group(1), m.group(3), m.group(2))
    # This is a bugfix for "what if" feed
    return result.replace('src="//', 'src="http://')

def substitute_latex(match):
    # FIXME wipe temporary files after work
    TEMP_PATH = tempfile.tempdir

    if match.group(0)[1] == '[':
        prefix = "<center>"
        postfix = "<center>"
    else:
        prefix = ""
        postfix = ""

    latex = urllib2.unquote(match.group(1))
    transform_result = subprocess.check_output(["texvc", TEMP_PATH, TEMP_PATH, latex])
    if transform_result[0] == "+":
        return prefix + '<img src="file://{0}/{1}.png" alt="{2}">'.format(TEMP_PATH, transform_result[1:], match.group(1)) + postfix

    if transform_result[0] in "cmlCML":
        return prefix + transform_result[33:] + postfix

    return match.group(0)

#================ Patched RecursiveFetcher ====================

class ImageFormat(object):
    """ Base class for image formats """
    def save(self, imgpath, data):
        """ Saves image to imgpath. Returns Trueon success,
            False if image must be skipped. """
        with open(imgpath, 'wb') as x:
            x.write(data)
        return True

class PngFormat(ImageFormat):
    extension = "png"
    def magic(self, data):
        return data[1:4] == "PNG"

class GifFormat(ImageFormat):
    extension = "gif"
    def magic(self, data):
        return data[0:3] == "GIF"

    def save(self, imgpath, data):
        if data == 'GIF89a\x01':
            # Skip empty GIF files as PIL errors on them anyway
            return False
        else:
            return super(GifFormat, self).save(imgpath, data)

class JpegFormat(ImageFormat):
    extension = "jpg"
    def magic(self, data):
        return data[0] == 0xFF and data[0] == "D9"

    def save(self, imgpath, data):
        """ This is fallback format too, so we will accept any image and save it to jpeg"""
        im = Image.open(StringIO(data)).convert('RGBA')
        # FIXME Use white background for transparent images
        with open(imgpath, 'wb') as x:
            im.save(x, 'JPEG')
        return True

class RichRecursiveFetcher(RecursiveFetcher):
    """ Nearly the same as RecursiveFetcher, but can be configured 
        not to repack png's and gis's in jpeg. API is compatible. """

    def __init__(self, *args, **kwargs):
        self._image_formats = kwargs.pop("image_formats", [JpegFormat()])
        super(RichRecursiveFetcher, self).__init__(*args, **kwargs)

    def process_images(self, soup, baseurl):
        diskpath = unicode_path(os.path.join(self.current_dir, 'images'))
        if not os.path.exists(diskpath):
            os.mkdir(diskpath)
        c = 0
        for tag in soup.findAll(lambda tag: tag.name.lower()=='img' and tag.has_key('src')):
            iurl = tag['src']
            if callable(self.image_url_processor):
                iurl = self.image_url_processor(baseurl, iurl)
            if not urlparse.urlsplit(iurl).scheme:
                iurl = urlparse.urljoin(baseurl, iurl, False)
            with self.imagemap_lock:
                if self.imagemap.has_key(iurl):
                    tag['src'] = self.imagemap[iurl]
                    continue

            #==== Changes begin here ====
            try:
                data = self.fetch_url(iurl)
            except Exception:
                self.log.exception('Could not fetch image ', iurl)
                continue

            c += 1
            fname = ascii_filename('img'+str(c))
            # Hm. Does ascii_filename return unicode names? Not touching.
            if isinstance(fname, unicode):
                fname = fname.encode('ascii', 'replace')

            for image_format in self._image_formats:
                # Use the last format as a fallback
                if image_format.magic(data) or image_format == self._image_formats[-1]:
                    imgpath = os.path.join(diskpath, fname + "." + image_format.extension)
                    try:
                        with self.imagemap_lock:
                            self.imagemap[iurl] = imgpath
                        if not image_format.save(imgpath, data):
                            break
                    except:
                        traceback.print_exc()
                        break

                    tag['src'] = imgpath

#================ end of patched RecursiveFetcher ====================

class DownloadedArticlesList(object):
    """ Remembers which articles were downloaded so as not to add them
        to export second time."""

    LIST_SIZE_LIMIT = 5000

    def __init__(self, file):
        self._file = file
        self._url_list = []
        self._url_set = set()
        try:
            with open(self._file, "r") as f:
                for line in f:
                    line = line.strip()
                    self._url_list.append(line)
                    self._url_set.add(line)
        except IOError:
            pass

    def __contains__(self, url):
        return url in self._url_set

    def add(self, url):
        self._url_list.append(url)
        self._url_set.add(url)

    def close(self):
        with open(self._file, "w") as f:
            self._url_list = self._url_list[-DownloadedArticlesList.LIST_SIZE_LIMIT:]
            for url in self._url_list:
                print >>f, url

class MultiFeedRecipe(AutomaticNewsRecipe):
    title          = u'RSS ' + time.strftime("%m %d")
    oldest_article = 7
    max_articles_per_feed = 200
    auto_cleanup = False
    ignore_duplicate_articles = None
    remove_empty_feeds = True

    # Do not rescale images
    scale_news_images_to_device = False
    compress_news_images = False
    compress_news_images_auto_size = None

    def build_index(self):
        #========== added =========
        downloaded_list = DownloadedArticlesList(self.download_history_file)
        #==========================

        self.report_progress(0, _('Fetching feeds...'))
        try:
            feeds = feeds_from_index(self.parse_index(), oldest_article=self.oldest_article,
                                     max_articles_per_feed=self.max_articles_per_feed,
                                     log=self.log)
            self.report_progress(0, _('Got feeds from index page'))
        except NotImplementedError:
            feeds = self.parse_feeds()

        #========== reworked =========
        for feed in feeds:
            feed.articles = filter(lambda article: article.url not in downloaded_list, feed.articles)

        # Filer out empty feeds
        if self.ignore_duplicate_articles is not None:
            feeds = self.remove_duplicate_articles(feeds)
        feeds = filter(lambda feed: len(feed.articles), feeds)
        if not feeds:
            raise ValueError('No articles found, aborting')
        #=============================

        #feeds = FeedCollection(feeds)

        self.has_single_feed = len(feeds) == 1

        index = os.path.join(self.output_dir, 'index.html')

        html = self.feeds2index(feeds)
        with open(index, 'wb') as fi:
            fi.write(html)

        self.jobs = []

        if self.reverse_article_order:
            for feed in feeds:
                if hasattr(feed, 'reverse'):
                    feed.reverse()

        self.feed_objects = feeds
        for f, feed in enumerate(feeds):
            feed_dir = os.path.join(self.output_dir, 'feed_%d'%f)
            if not os.path.isdir(feed_dir):
                os.makedirs(feed_dir)

            for a, article in enumerate(feed):
                #========== refactored =========
                art_dir = os.path.join(feed_dir, 'article_%d'%a)
                if not os.path.isdir(art_dir):
                    os.makedirs(art_dir)
              
                downloaded_list.add(article.url) 
                url = self.feed_settings[feed.title].print_version_url(article.url)

                req = WorkRequest(
                    self.feed_settings[feed.title].fetch,
                    (self, article, url, art_dir, f, a, len(feed)),
                                      {}, (f, a), self.article_downloaded,
                                      self.error_in_article_download)
                #===============================
                req.feed = feed
                req.article = article
                req.feed_dir = feed_dir
                self.jobs.append(req)

        self.jobs_done = 0
        tp = ThreadPool(self.simultaneous_downloads)
        for req in self.jobs:
            tp.putRequest(req, block=True, timeout=0)

        self.report_progress(0, _('Starting download [%d thread(s)]...')%self.simultaneous_downloads)
        while True:
            try:
                tp.poll()
                time.sleep(0.1)
            except NoResultsPending:
                break

        for f, feed in enumerate(feeds):
            html = self.feed2index(f,feeds)
            feed_dir = os.path.join(self.output_dir, 'feed_%d'%f)
            with open(os.path.join(feed_dir, 'index.html'), 'wb') as fi:
                fi.write(html)
        self.create_opf(feeds)
        self.report_progress(1, _('Feeds downloaded to %s')%index)

        #========== added =========
        downloaded_list.close()
        #==========================

        return index

    def _fetch_article(self, url, dir_, f, a, num_of_feeds):
        br = self.browser
        if self.get_browser.im_func is BasicNewsRecipe.get_browser.im_func:
            # We are using the default get_browser, which means no need to
            # clone
            br = BasicNewsRecipe.get_browser(self)
        else:
            br = self.clone_browser(self.browser)
        self.web2disk_options.browser = br
        # ============== Here is the only change =================
        fetcher = RichRecursiveFetcher(self.web2disk_options, self.log,
                self.image_map, self.css_map,
                (url, f, a, num_of_feeds),
                image_formats=[PngFormat(), GifFormat(), JpegFormat()])
        # ========================================================
        fetcher.browser = br
        fetcher.base_dir = dir_
        fetcher.current_dir = dir_
        fetcher.show_progress = False
        fetcher.image_url_processor = self.image_url_processor
        res, path, failures = fetcher.start_fetch(url), fetcher.downloaded_paths, fetcher.failed_links
        if not res or not os.path.exists(res):
            msg = _('Could not fetch article.') + ' '
            if self.debug:
                msg += _('The debug traceback is available earlier in this log')
            else:
                msg += _('Run with -vv to see the reason')
            raise Exception(msg)

        return res, path, failures

    def _postprocess_html(self, soup, first_fetch, job_info):
        if self.no_stylesheets:
            for link in list(soup.findAll('link', type=re.compile('css')))+list(soup.findAll('style')):
                link.extract()
        head = soup.find('head')
        if not head:
            head = soup.find('body')
        if not head:
            head = soup.find(True)
        style = BeautifulSoup(u'<style type="text/css" title="override_css">%s</style>'%(
            self.template_css +'\n\n'+(self.extra_css if self.extra_css else ''))).find('style')
        head.insert(len(head.contents), style)
        if first_fetch and job_info:
            url, f, a, feed_len = job_info
            body = soup.find('body')
            if body is not None:
                templ = self.navbar.generate(False, f, a, feed_len,
                                             not self.has_single_feed,
                                             url, __appname__,
                                             center=self.center_navbar,
                                             extra_css=self.extra_css)
                elem = BeautifulSoup(templ.render(doctype='xhtml').decode('utf-8')).find('div')
                body.insert(0, elem)
        if self.remove_javascript:
            for script in list(soup.findAll('script')):
                script.extract()
            for o in soup.findAll(onload=True):
                del o['onload']

        for script in list(soup.findAll('noscript')):
            script.extract()
        for attr in self.remove_attributes:
            for x in soup.findAll(attrs={attr:True}):
                del x[attr]
        for base in list(soup.findAll(['base', 'iframe', 'canvas', 'embed',
            'command', 'datalist', 'video', 'audio'])):
            base.extract()

        # ============== Here is the only change =================
        # Soup seems to be rotten. Don't know why. Recook it.
        soup = BeautifulSoup(str(soup))
        ans = self.postprocess_html(soup, first_fetch)
        if first_fetch and job_info:
            postprocessor = self.feed_settings[self.feed_objects[f].title].postprocess_html
            ans = postprocessor(soup, first_fetch)
        # ========================================================

        # Nuke HTML5 tags
        for x in ans.findAll(['article', 'aside', 'header', 'footer', 'nav',
            'figcaption', 'figure', 'section']):
            x.name = 'div'

        if job_info:
            url, f, a, feed_len = job_info
            try:
                article = self.feed_objects[f].articles[a]
            except:
                self.log.exception('Failed to get article object for postprocessing')
                pass
            else:
                self.populate_article_metadata(article, ans, first_fetch)
        return ans
