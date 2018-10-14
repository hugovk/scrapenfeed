""""Scrape 'N' Feed
Simple PyRSS2Gen wrapper for screen-scraping RSS feeds
http://www.crummy.com/software/ScrapeNFeed"""

__author__ = "Leonard Richardson (leonardr@segfault.org)"
__version__ = "1.0.0"
__copyright__ = "Copyright (c) 2005 Leonard Richardson"
__license__ = "PSF"

import datetime
import hashlib
import os
import pickle
import time
import traceback
import urllib
from urllib.parse import urlparse, urljoin
from io import BytesIO
from PyRSS2Gen import RSS2, RSSItem, Guid

hdr = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11',
       'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
       'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
       'Accept-Encoding': 'none',
       'Accept-Language': 'en-US,en;q=0.8',
       'Connection': 'keep-alive'}

class WebPageMetadata:
    """Keeps track of the most recent Last-Modified and Etag headers
    obtained for a particular web page."""

    def __init__(self, url, pickleFile=None, etag=None, lastModified=None):
        self.url=url
        self.baseURL = urljoin(url, ' ')[:-1]
        if not pickleFile:
            pickleFile = self.digest() + '.pickle'
        self.pickleFile = pickleFile
        self.etag = etag
        self.lastModified = lastModified

    def digest(self):
        m = hashlib.md5.new()
        m.update(self.url)
        return m.hexdigest()

    def pickle(self):
        s = BytesIO()
        pickle.dump(self, s)
        f = open(self.pickleFile, 'wb')
        f.write(s.getvalue())
        f.close()

    def fetch(self):
        request = urllib.request.Request(self.url, headers=hdr)
        if self.etag:
            request.add_header('If-None-Match', self.etag)
        if self.lastModified:
            request.add_header('If-Modified-Since', self.lastModified)
        response = urllib.request.urlopen(request)

        headers = response.info()
        self.etag = headers.get('ETag', None)
        self.lastModified = headers.get('Last-Modified', None)
        return response

class ScrapedFeed(RSS2, WebPageMetadata):
    """This class makes it easy to maintain an RSS feed that's somehow derived
    from a web page."""

    def __init__(self, title, url, description, rssFile=None, pickleFile=None,
                 maxItems=20, **kwargs):
        RSS2.__init__(self, title, url, description, **kwargs)
        WebPageMetadata.__init__(self, url, pickleFile)
        self.maxItems = maxItems
        if not rssFile:
            rssFile = self.digest() + '.xml'
        self.rssFile = rssFile
        self.currentGuids = {}

    def refresh(self):
        """Re-fetches the source of this feed, updates the RSS feed
        representation to match, outputs a new RSS feed in XML format,
        and pickles the new state of the feed."""

        try:
            response = self.fetch()
            headers = response.info()
            body = response.read()
            self.lastBuildDate = datetime.datetime.now()
            try:
                self.HTML2RSS(headers, body)
            except Exception as e:
                #Put the exception into the RSS feed.
                import sys
                exception = traceback.format_tb(e.__traceback__)
                description="<p>Unable to finish scraping this webpage into a feed. Please get the person in charge of maintaining the scraped feed (<i>not</i> the person in charge of the original website) to fix this.</p> <p>Stack trace:</p> <pre>%s%s</pre>" % ('\n'.join(exception), e)
                self.pushRSSItem(RSSItem(link=self.url + '#' + str(time.time()),
                                         title='Error scraping this feed',
                                         description=description))
            self.writeRSS()
            self.pickle()
        except urllib.error.HTTPError as e:
            if e.code == 304:
                #The page hasn't been modified. Doing nothing is exactly
                #the right thing to do.
                pass
            else:
                raise e

    def writeRSS(self):
        f = open(self.rssFile, 'wb')
        self.write_xml(f)
        f.close()

    def hasSeen(self, guid):
        "Returns true iff the given guid is already present in this feed."
        if isinstance(guid, Guid):
            guid = guid.guid
        return self.currentGuids.get(guid, False)

    def addRSSItems(self, items):
        """Adds a number of RSS items to the top of an RSS feed.  If
        the resulting feed is longer than the maximum number of items,
        and some of those items were put on the feed in previous runs,
        the earliest such items will be shifted off the feed."""
        for i in items[::-1]:
            self.pushRSSItem(i)

    def pushRSSItem(self, item):
        """Adds an RSS Item to the top of an RSS feed. If the
        resulting feed is longer than the maximum number of items, and
        some of those items were put on the feed in previous runs, the
        earliest such item will be shifted off the feed."""
        if not getattr(item, 'guid') and item.link:
            item.guid = Guid(item.link)
        if not getattr(item, 'pubDate'):
            item.pubDate = self.lastBuildDate

        #Stringify data from external sources (eg. Beautiful Soup) to
        #avoid complications with pickling.
        for field in ('title', 'link', 'description', 'author', 'category',
                      'comments',' source'):
            s = getattr(item, field, None)
            if s:
                setattr(item, field, str(s))

        if self.hasSeen(item.guid):
            #print "Checking for newer version of %s", item.guid.guid
            #This item is already in this feed. Replace it with the possibly
            #new version.
            for i in range(0, len(self.items)):
                check = self.items[i]
                if check.guid.guid == item.guid.guid:
                    #print "Updating possibly old version of %s" % item.guid.guid
                    self.items[i] = item
                    break
        else:
            #We haven't seen this item before, so the new one can go in.
            #print "Inserting ", item.guid.guid
            self.items.insert(0, item)
            self.currentGuids[item.guid.guid] = self.lastBuildDate
        while len(self.items) > self.maxItems \
            and self.currentGuids.get(self.items[-1].guid.guid) != self.lastBuildDate:
            #There are too many items in the feed, and the oldest one
            #was inserted in a previous update, so we can get rid of
            #it.
            #print "%s pushed off the edge!" % self.items[-1].guid.guid
            old = self.items.pop(-1)
            del(self.currentGuids[old.guid.guid])

    def HTML2RSS(self, headers, body):
        """Override this method to build an RSS feed out of the given
        HTTP response. This method should construct a number of
        PyRSS2Gen.RSSItem objects and call self.addItem() on each
        one. You may pass in your guid to self.hasSeen() if you want
        to see whether or not to bother creating a particular
        RSSItem that might already be in the feed."""

        raise Exception("""Hey buddy! You forgot to override the HTML2RSS method
        which actually creates the RSS feed out of a web page!""")

    def load(subclass, title, url, description, rssFile=None,
             pickleFile=None, maxItems=20, refresh=True, **kwargs):
        if pickleFile and os.path.exists(pickleFile):
            f = open(pickleFile, 'rb')
            feed = pickle.load(f)
            feed.title = title
            feed.description = description
            feed.rssFile=rssFile
            feed.maxItems = maxItems
        else:
            feed = subclass(title, url, description, rssFile, pickleFile, maxItems, **kwargs)
        if refresh:
            feed.refresh()
        return feed
    load = classmethod(load)
