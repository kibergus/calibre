calibre
=======

calibre RSS addon

Creates single books from multiple RSS streams. Features:
 * Separate settings for every feed
 * Does not transcode png and gif to jpeg (kindle can show them natively)
 * Renders latex formulae from What If blog
 * Greasemonkey userscript which allows to populate custom RSS feed with articles from habrahabr
 * Simple user populatable RSS feed implementation

Dependencies:
 * calibre - calibre-ebook.com
 * mediawiki-math-texvc - to render latex formulae
 * php - for RSS feed
 * firefox + greasemmonkey or opera - for userscript

Installation:
 * Install mediawiki-math-texvc
 * Put feed_settings.py and multy_feed.py to /usr/lib/calibre/calibre/web/feeds
 * Upload rss_feed.php to your server, rename it and adjust storage file name in script
 * Change address of rss feed in Habr2kindle.user.js and add it to your browser
 * Put example.recipe to a convinient place and adjust accordingly to your needs

Usage:
 * ebook-convert example.recipe news.mobi --no-inline-toc --mobi-keep-original-images --output-profile=kindle
