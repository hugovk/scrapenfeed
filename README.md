# Scrape 'N' Feed

[Scrape 'N' Feed](https://www.crummy.com/software/ScrapeNFeed/) by Leonard Richardson is a simple Python wrapper around the [PyRSS2Gen](http://www.dalkescientific.com/Python/PyRSS2Gen.html) module. It implements almost all of the code you need to create RSS feeds out of web pages. All you have to write is the code that actually does the screen-scraping (and [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/) makes that easy). It stores feed state in a pickle file between invocations, freeing you from having to worry about most of the minor problems that get in the way of scraping RSS feeds.

## Generic Example

This example should give you an idea of how Scrape 'N' Feed interacts with the PyRSS2Gen module.

```python
#!/usr/bin/env python
import ScrapeNFeed

class MyFeed(ScrapeNFeed.ScrapedFeed):    

    def HTML2RSS(self, headers, body):

	#Transform an HTTP response into a series of RSSItem objects
        items = []
	...
        #Scrape scrape scrape... 
	...
	#Then add the items to the feed.
        self.addRSSItems(items)

#Load the feed with its metadata. This will fetch the URL, scrape it
#for RSSItems, and possibly write out new RSS and pickle files.
MyFeed.load('Feed title',
            'Feed source: the URL to fetch and pass into HTML2RSS',
            'Feed description'
            'Path to destination RSS file', 
            'Path to pickle file containing feed state',
	    [Any other arguments you'd pass into the RSS2 constructor])
```

## Specific Example

This example generates [this RSS feed](https://www.crummy.com/software/ScrapeNFeed/oreilly.xml) out of the[ list of upcoming books from O'Reilly](http://www.oreilly.com/catalog/new.html).

```python
#!/usr/bin/env python
import BeautifulSoup
from PyRSS2Gen import RSSItem, Guid
import ScrapeNFeed

class OReillyFeed(ScrapeNFeed.ScrapedFeed):    

    def HTML2RSS(self, headers, body):
        soup = BeautifulSoup.BeautifulSoup(body)
        headerText = soup.firstText('Upcoming Titles')
        titleList = headerText.findNext('ul')
        items = []
        for item in titleList('li'):
            link = self.baseURL + item.a['href']
            if not self.hasSeen(link):
                bookTitle = item.a.string
                releaseDate = item.em.string
                items.append(RSSItem(title=bookTitle,
                                     description=releaseDate,
                                     link=link))
        self.addRSSItems(items)

OReillyFeed.load("Newly announced O'Reilly books",
                 'http://www.oreilly.com/catalog/new.html',
                 "Keep track of O'Reilly books as they're announced",
                 'oreilly.xml', 
		 'oreilly.pickle',
                 managingEditor='leonardr@segfault.org (Leonard Richardson)')
```

Run this code once a day from a cron, and you'll have an up-to-date feed kept in oreilly.xml. The feed information is serialized to oreilly.pickle. The feed generated is a real PyRSS2Gen RSS2 object with real RSSItems in it, so you can put in any special PyRSS2Gen code you might need.

## The Scrape 'N' Feed Advantage

Scrape 'N' Feed handles as much as possible of the work of turning a web page into an RSS feed, leaving you free to concentrate on the scraping code.

 * Scrape 'N' Feed saves you from having to write code to fetch the page. It respects the ETag and Last-Modified HTTP headers, which saves time and bandwidth over multiple runs.
 * As new items are put into the RSS feed, older items are automatically pushed out. A feed has a maximum length, but the maximum length can be temporarily violated if a single update yields a lot of new items. For instance, if the maximum feed length is 20, but an update reveals 25 new items, the feed will contain all 25 new items until the next update.
 * The items on some sites (such as the O'Reilly site) have no publication dates. This is no problem for Scrape 'N' Feed. It keeps track of when a link was seen for a feed, and it will use that date as the publication date if no other date is provided.
 * GUIDs are automatically created from the item links (If you want to create custom GUIDs, or if the page you're scraping doesn't have permalinks to each item, you can still create GUIDs manually).
 * Exceptions thrown while screen-scraping are turned into notifications in the RSS feed, so you're more likely to see them.
