# -*- coding: utf-8 -*-
import datetime
import re
import requests
import json
from bs4 import BeautifulSoup

def get_text(element: BeautifulSoup | None):
	if element is not None:
		return element.get_text()
	return ""


def get_xml(url, headers=None):
	print(f"Sending GET to '{url}'")
	res = None
	if headers:
		res = requests.get(url=url, headers=headers)
	else:
		res = requests.get(url=url)
	print(f"Response status: HTTP {res.status_code}")
	if res.status_code >= 400:
		return
	res.encoding = "utf-8"
	print(f"Got response of size '{len(res.text)}'")
	return BeautifulSoup(res.text, "xml")


def std_datetime(date):
	return (
		date
		.astimezone(tz=datetime.timezone.utc)
		.isoformat()
	)


def letterboxd():
	soup = get_xml("https://letterboxd.com/matheusavellar/rss/")
	if soup is None:
		return []

	output = []
	for review in soup.find_all("item"):
		# <item>
		# 	<title>Ne Zha, 2019 - ★★★½</title>
		# 	<link>https://letterboxd.com/matheusavellar/film/ne-zha/</link>
		# 	<guid isPermaLink="false">letterboxd-review-964046536</guid>
		# 	<pubDate>Tue, 29 Jul 2025 13:03:10 +1200</pubDate>
		# 	<letterboxd:watchedDate>2025-07-28</letterboxd:watchedDate>
		# 	<letterboxd:rewatch>No</letterboxd:rewatch>
		# 	<letterboxd:filmTitle>Ne Zha</letterboxd:filmTitle>
		# 	<letterboxd:filmYear>2019</letterboxd:filmYear>
		# 	<letterboxd:memberRating>3.5</letterboxd:memberRating>
		# 	<tmdb:movieId>615453</tmdb:movieId>
		# 	<description>
		# 		<![CDATA[
		# 			<p>
		# 				<img src="https://a.ltrbxd.com/resized/film-poster/5/4/2/3/4/1/542341-ne-zha-0-600-0-900-crop.jpg?v=286c1db228"/>
		# 			</p>
		# 			<p> ... </p>
		# 		]]>
		# 	</description>
		# 	<dc:creator>Matheus Avellar</dc:creator>
		# </item>
		review_url = get_text(review.find("link"))
		pubDate = get_text(review.find("pubDate"))
		dt = datetime.datetime.strptime(pubDate, "%a, %d %b %Y %H:%M:%S %z")
		# If this event is older than a month, ignore it
		if dt < (datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(days=30)):
			continue
		review_datetime = std_datetime(dt)
		watched_date = get_text(review.find("letterboxd:watchedDate"))
		is_rewatch = get_text(review.find("letterboxd:rewatch")) != "No"
		film_title = get_text(review.find("letterboxd:filmTitle"))
		film_year = get_text(review.find("letterboxd:filmYear"))
		rating = get_text(review.find("letterboxd:memberRating"))
		tmdb_id = get_text(review.find("tmdb:movieId"))
		description = get_text(review.find("description"))
		# poster_url = (re.search(r"<img src=\"([^\"]+)\"", description) or [0,""])[1]
		output.append({
			"url": review_url,
			"datetime": review_datetime,
			"title": f"{film_title} ({film_year})" if film_year else film_title,
			"type": "letterboxd",
			"details": {
				"event": "review",
				"watched_date": watched_date,
				"is_rewatch": is_rewatch,
				"raw_title": film_title,
				"raw_year": film_year,
				"rating": rating,
				"tmdb_id": tmdb_id,
				# "poster_url": poster_url
			}
		})
	print(f"Finished reading XML; got {len(output)} entries. Limiting to latest 10")
	output.sort(reverse=True, key=lambda obj: datetime.datetime.fromisoformat(obj["datetime"]))
	return output


def wikipedia():
	params = "action=feedcontributions&feedformat=atom&user=Avelludo"
	urls = [
		f"https://en.wikipedia.org/w/api.php?{params}",
		f"https://commons.wikimedia.org/w/api.php?{params}",
		f"https://pt.wikipedia.org/w/api.php?{params}",
	]
	output = []
	default_headers = requests.utils.default_headers() 
	default_ua = default_headers["User-Agent"] if "User-Agent" in default_headers else ""
	custom_ua = f"AvelludoRSS/0.0 (https://en.wikipedia.org/wiki/User:Avelludo; selfrss@avl.la) {default_ua}".strip()

	for url in urls:
		# [Ref] https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy
		soup = get_xml(url, headers={ "User-Agent": custom_ua })
		if soup is None:
			continue

		for entry in soup.find_all("entry"):
			# <entry>
			# 	<id>https://en.wikipedia.org/w/index.php?title=Brazilian_real&diff=1303551938</id>
			# 	<title>Brazilian real</title>
			# 	<link rel="alternate" type="text/html" href="https://en.wikipedia.org/w/index.php?title=Brazilian_real&diff=1303551938"/>
			# 	<updated>2025-07-31T17:23:10Z</updated>
			# 	<summary type="html">
			# 		<p>Avelludo: ...</p> <hr />...
			# 	</summary>
			# 	<author><name>Avelludo</name></author>
			# </entry>
			edit_url = get_text(entry.find("id"))
			page_title = get_text(entry.find("title"))
			updated = get_text(entry.find("updated"))
			dt = datetime.datetime.strptime(updated, "%Y-%m-%dT%H:%M:%S%z")
			# If this event is older than a month, ignore it
			if dt < (datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(days=30)):
				continue
			edit_datetime = std_datetime(dt)
			summary = get_text(entry.find("summary"))
			edit_description = (
				summary
				.removeprefix("<p>Avelludo: ")
				.split("</p>")[0]
				.strip()
			)
			# Edits to structured data
			if edit_description == "/* wbeditentity-update:0| */":
				continue

			event = "edit-page"
			if edit_description.startswith("Uploaded a work"):
				event = "file-upload";
			elif edit_description.lower().startswith("create article") \
				or edit_description.lower().startswith("create category") \
				or edit_description.lower().startswith("create draft") \
				or edit_description.lower().startswith("cria artigo") \
				or edit_description.lower().startswith("cria categoria") \
				or edit_description.lower().startswith("cria rascunho"):
				event = "create-article";

			wiki_prefix = url.removeprefix("https://").split(".")[0]
			output.append({
				"url": edit_url,
				"datetime": edit_datetime,
				"title": page_title,
				"type": "wiki",
				"details": {
					"event": event,
					"kind": wiki_prefix,
					"description": edit_description
				}
			})
	print(f"Finished reading XML; got {len(output)} entries. Limiting to latest 10")
	output.sort(reverse=True, key=lambda obj: datetime.datetime.fromisoformat(obj["datetime"]))
	return output


def mal():
	soup = get_xml("https://myanimelist.net/rss.php?type=rwe&u=Beta-Tester")
	if soup is None:
		return []

	output = []
	for item in soup.find_all("item"):
		# <item>
		# 	<title>FLCL</title>
		# 	<link>https://myanimelist.net/anime/227/FLCL</link>
		# 	<guid>https://myanimelist.net/anime/227/FLCL</guid>
		# 	<description>
		# 		<![CDATA[ Completed - 6 of 6 episodes ]]>
		# 	</description>
		# 	<pubDate>Tue, 29 Jul 2025 23:15:47 -0300</pubDate>
		# </item>
		anime_title = item.find("title").get_text()
		anime_url = item.find("link").get_text()
		description = item.find("description").get_text()
		matches = re.search(r"(?P<status>.+) - (?P<watched>[0-9]+) of (?P<total>[0-9]+) episodes", description)
		watch_status = None
		episodes_watched = None
		episodes_total = None
		if matches:
			watch_status = matches.group("status")
			episodes_watched = matches.group("watched")
			episodes_total = matches.group("total")
		pubDate = item.find("pubDate").get_text()
		dt = datetime.datetime.strptime(pubDate, "%a, %d %b %Y %H:%M:%S %z")
		# If this event is older than a month, ignore it
		if dt < (datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(days=30)):
			continue
		update_datetime = std_datetime(dt)
		output.append({
			"url": anime_url,
			"datetime": update_datetime,
			"title": anime_title,
			"type": "mal",
			"details": {
				"event": "watch",
				"status": watch_status,
				"episodes_watched": episodes_watched,
				"episodes_total": episodes_total
			}
		})
	print(f"Finished reading XML; got {len(output)} entries. Limiting to latest 10")
	output.sort(reverse=True, key=lambda obj: datetime.datetime.fromisoformat(obj["datetime"]))
	return output


def github():
	# https://docs.github.com/en/rest/activity/events?apiVersion=2022-11-28#list-public-events-for-a-user
	GH_ENDPOINT = "https://api.github.com/users/MatheusAvellar/events/public"
	print(f"Sending GET to '{GH_ENDPOINT}'")
	res = requests.get(
		url=GH_ENDPOINT,
		headers={
			"Accept": "application/vnd.github+json",
			"X-GitHub-Api-Version": "2022-11-28"
		}
	)
	print(f"Response status: HTTP {res.status_code}")
	if res.status_code >= 400:
		return
	res.encoding = "utf-8"
	print(f"Got response of size '{len(res.text)}'")

	res_obj = res.json()
	output = []
	for evt in res_obj:
		# {
		# 	"id": "53876916926",
		# 	"type": "...",
		# 	"actor": {
		# 		"id": 1719996,
		# 		"login": "MatheusAvellar",
		# 		"display_login": "MatheusAvellar",
		# 		"gravatar_id": "",
		# 		"url": "https://api.github.com/users/MatheusAvellar",
		# 		"avatar_url": "https://avatars.githubusercontent.com/u/1719996?"
		# 	},
		# 	"repo": {
		# 		"id": ...,
		# 		"name": "...",
		# 		"url": "..."
		# 	},
		# 	"payload": { ... },
		# 	"public": true,
		# 	"created_at": "2025-08-27T01:25:46Z",
		# 	"org": {
		# 		"id": ...,
		# 		"login": "...",
		# 		"gravatar_id": "",
		# 		"url": "...",
		# 		"avatar_url": "..."
		# 	}
		# },
		event_type = evt["type"]
		if event_type == "PushEvent":
			continue

		created = evt["created_at"]
		dt = datetime.datetime.strptime(created, "%Y-%m-%dT%H:%M:%S%z")
		# If this event is older than a month, ignore it
		month_ago = (
			datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(days=30)
		)
		if dt < month_ago:
			continue

		event_datetime = std_datetime(dt)
		repository = evt["repo"]["name"]
		event_description = ""
		event_url = f"https://github.com/{repository}"

		payload = evt["payload"]
		# Pull request
		if event_type == "PullRequestEvent":
			action = payload["action"].capitalize()
			pr = payload["pull_request"]
			from_branch = pr["head"]["ref"]
			to_branch = pr["base"]["ref"]
			event_description = f"{action} pull request ('{from_branch}' → '{to_branch}')"
			event_url = pr["html_url"]
		# Create, Delete
		elif event_type == "CreateEvent" or event_type == "DeleteEvent":
			created_type = payload["ref_type"]
			created_name = payload["ref"]
			name = f"'{created_name}'" if created_name else ""
			event_verb = "Created" if event_type == "CreateEvent" else "Deleted"
			event_description = f"{event_verb} {created_type} {name}".strip()
		# Fork
		elif event_type == "ForkEvent":
			forked_to = payload["forkee"]["full_name"]
			event_description = f"Forked to '{forked_to}'"
			event_url = payload["forkee"]["html_url"]
		# Star
		elif event_type == "WatchEvent":
			if payload["action"] == "started":
				event_description = "Starred repository"
			else:
				event_description = "Unstarred repository"
		# Issue
		elif event_type == "IssuesEvent":
			action = payload["action"].capitalize()
			event_description = f"{action} issue"
			event_url = payload["issue"]["html_url"]
		# Make repository public
		elif event_type == "PublicEvent":
			event_description = f"Made public"
		# Release version
		elif event_type == "ReleaseEvent":
			action = payload["action"].capitalize()
			tag = payload["release"]["name"]
			event_description = f"{action} to '{tag}'"
			event_url = payload["release"]["html_url"]
		else:
			print(f"Unrecognized event '{event_type}', please add it")
			continue

		output.append({
			"url": event_url,
			"datetime": event_datetime,
			"title": repository,
			"type": "github",
			"details": {
				"kind": "github",
				"event": event_type,
				"description": event_description,
			}
		})
	print(f"Finished reading JSON; got {len(output)} entries. Limiting to latest 10")
	output.sort(reverse=True, key=lambda obj: datetime.datetime.fromisoformat(obj["datetime"]))
	return output


def gist():
	# https://docs.github.com/en/rest/gists/gists?apiVersion=2022-11-28#list-public-gists
	GH_ENDPOINT = "https://api.github.com/users/MatheusAvellar/gists"
	print(f"Sending GET to '{GH_ENDPOINT}'")
	res = requests.get(
		url=GH_ENDPOINT,
		headers={
			"Accept": "application/vnd.github+json",
			"X-GitHub-Api-Version": "2022-11-28"
		}
	)
	print(f"Response status: HTTP {res.status_code}")
	if res.status_code >= 400:
		return
	res.encoding = "utf-8"
	print(f"Got response of size '{len(res.text)}'")

	res_obj = res.json()
	output = []
	for evt in res_obj:
		# {
		# 	"url": "https://api.github.com/gists/...",
		# 	"forks_url": "https://api.github.com/gists/.../forks",
		# 	"commits_url": "https://api.github.com/gists/.../commits",
		# 	"id": "...",
		# 	"node_id": "...",
		# 	"git_pull_url": "https://gist.github.com/....git",
		# 	"git_push_url": "https://gist.github.com/....git",
		# 	"html_url": "https://gist.github.com/MatheusAvellar/...",
		# 	"files": { ... },
		# 	"public": true,
		# 	"created_at": "2025-08-12T16:06:35Z",
		# 	"updated_at": "2025-08-12T17:14:03Z",
		# 	"description": "...",
		# 	"comments": 1,
		# 	"user": null,
		# 	"comments_enabled": true,
		# 	"comments_url": "https://api.github.com/gists/bc0d1ec99b3559c9aaa0d676c2e5324b/comments",
		# 	"owner": { ... },
		# 	"truncated": false
		# },
		created = evt["created_at"]
		dt = datetime.datetime.strptime(created, "%Y-%m-%dT%H:%M:%S%z")
		# If this event is older than a month, ignore it
		month_ago = (
			datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(days=30)
		)
		if dt < month_ago:
			continue
		event_datetime = std_datetime(dt)

		title = evt["description"]
		event_description = ""
		event_url = evt["html_url"]

		output.append({
			"url": event_url,
			"datetime": event_datetime,
			"title": title,
			"type": "github",
			"details": {
				"kind": "gist",
				"event": "GistEvent"
			}
		})
	print(f"Finished reading JSON; got {len(output)} entries. Limiting to latest 10")
	output.sort(reverse=True, key=lambda obj: datetime.datetime.fromisoformat(obj["datetime"]))
	return output


# Flickr:
# https://www.flickr.com/services/feeds/photos_public.gne?id=202939403@N02


def goodreads():
	custom_ua = "Mozilla/5.0 (Windows NT 10.0; selfrss@avl.la) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"
	#####################
	## General updates ##
	#####################
	soup = get_xml(
		"https://www.goodreads.com/review/list_rss/193877929",
		headers={ "User-Agent": custom_ua }
	)

	books = dict()
	output = []
	if soup is None:
		print(f"Failed reading first XML")
	else:
		for entry in soup.find_all("item"):
			# <item>
			# 	<guid><![CDATA[https://www.goodreads.com/review/show/7918416850?utm_medium=api&utm_source=rss]]></guid>
			# 	<pubDate><![CDATA[Mon, 15 Sep 2025 18:12:35 -0700]]></pubDate>
			# 	<title>Arrival</title>
			# 	<link><![CDATA[https://www.goodreads.com/review/show/7918416850?utm_medium=api&utm_source=rss]]></link>
			# 	<book_id>31625351</book_id>
			# 	<book_image_url><![CDATA[https://i.gr-assets.com/images/S/compressed.photo.goodreads.com/books/1478010711l/31625351._SY75_.jpg]]></book_image_url>
			# 	<book_small_image_url><![CDATA[https://i.gr-assets.com/images/S/compressed.photo.goodreads.com/books/1478010711l/31625351._SY75_.jpg]]></book_small_image_url>
			# 	<book_medium_image_url><![CDATA[https://i.gr-assets.com/images/S/compressed.photo.goodreads.com/books/1478010711l/31625351._SX98_.jpg]]></book_medium_image_url>
			# 	<book_large_image_url><![CDATA[https://i.gr-assets.com/images/S/compressed.photo.goodreads.com/books/1478010711l/31625351._SY475_.jpg]]></book_large_image_url>
			# 	<book_description><![CDATA[From a soaring Babylonian tower that connects a flat Earth with the heavens above, to a world where angelic visitations are a wondrous and terrifying part of everyday life; from a neural modification that eliminates the appeal of physical beauty, to an alien language that challenges our very perception of time and reality... Chiang's rigorously imagined stories invite us to question our understanding of the universe and our place in it.]]></book_description>
			# 	<book id="31625351">
			# 		<num_pages>304</num_pages>
			# 	</book>
			# 	<author_name>Ted Chiang</author_name>
			# 	<isbn>0525433678</isbn>
			# 	<user_name>Matheus</user_name>
			# 	<user_rating>0</user_rating>
			# 	<user_read_at></user_read_at>
			# 	<user_date_added><![CDATA[Mon, 15 Sep 2025 18:12:35 -0700]]></user_date_added>
			# 	<user_date_created><![CDATA[Mon, 15 Sep 2025 17:43:39 -0700]]></user_date_created>
			# 	<user_shelves>to-read</user_shelves>
			# 	<user_review></user_review>
			# 	<average_rating>4.10</average_rating>
			# 	<book_published>2002</book_published>
			# 	<description>
			# 		<![CDATA[
			# 			<a href="https://www.goodreads.com/book/show/31625351-arrival?utm_medium=api&amp;utm_source=rss"><img alt="Arrival" src="https://i.gr-assets.com/images/S/compressed.photo.goodreads.com/books/1478010711l/31625351._SY75_.jpg" /></a><br/>
			# 			author: Ted Chiang<br/>
			# 			name: Matheus<br/>
			# 			average rating: 4.10<br/>
			# 			book published: 2002<br/>
			# 			rating: 0<br/>
			# 			read at: <br/>
			# 			date added: 2025/09/15<br/>
			# 			shelves: to-read<br/>
			# 			review: <br/><br/>
			# 		]]>
			# 	</description>
			# </item>

			review_url = get_text(entry.find("link"))
			pubDate = get_text(entry.find("pubDate"))
			dt = datetime.datetime.strptime(pubDate, "%a, %d %b %Y %H:%M:%S %z")
			# If this event is older than a month, ignore it
			if dt < (datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(days=30)):
				continue
			review_datetime = std_datetime(dt)
			book_title = get_text(entry.find("title"))
			book_year = get_text(entry.find("book_published"))
			books[book_title] = book_year
			rating = get_text(entry.find("user_rating"))
			isbn = get_text(entry.find("isbn"))
			description = get_text(entry.find("description"))
			author_name = get_text(entry.find("author_name"))
			shelves = get_text(entry.find("user_shelves"))
			# cover_url = get_text(entry.find("book_small_image_url"))
			output.append({
				"url": review_url,
				"datetime": review_datetime,
				"title": f"{book_title.split(':')[0]} ({book_year})" if book_year else book_title,
				"type": "goodreads",
				"details": {
					"event": "added",
					"raw_title": book_title,
					"raw_year": book_year,
					"author": author_name,
					"rating": rating if rating != "0" else "",
					"shelves": shelves,
					"isbn": isbn,
					# "cover_url": cover_url
				}
			})


	#####################
	## Page updates    ##
	#####################
	soup = get_xml(
		"https://www.goodreads.com/user_status/list/193877929-matheus-avellar?format=rss",
		headers={ "User-Agent": custom_ua }
	)
	if soup is None:
		print(f"Failed reading second XML; got {len(output)} entries. Limiting to latest 10")
		return output.sort(reverse=True, key=lambda obj: datetime.datetime.fromisoformat(obj["datetime"]))

	for entry in soup.find_all("item"):
		# <item>
		# 	<title>Matheus Avellar is on page 70 of 432 of Tales of Old Japan</title>
		# 	<description></description>
		# 	<pubDate>Fri, 03 Oct 2025 05:35:46 -0700</pubDate>
		# 	<guid>https://www.goodreads.com/user_status/show/1140465388</guid>
		# 	<link>https://www.goodreads.com/user_status/show/1140465388</link>
		# </item>
		review_url = get_text(entry.find("link"))
		pubDate = get_text(entry.find("pubDate"))
		dt = datetime.datetime.strptime(pubDate, "%a, %d %b %Y %H:%M:%S %z")
		# If this event is older than a month, ignore it
		if dt < (datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(days=30)):
			continue
		review_datetime = std_datetime(dt)

		title = get_text(entry.find("title"))
		matches = re.search(r"^.+ is on page (?P<read>[0-9]+) of (?P<total>[0-9]+) of (?P<title>.+)$", title)
		if matches is None:
			print(f"Unrecognized Goodreads event: '{title}'")
		pages_read = matches.group("read")
		pages_total = matches.group("total")
		book_title = matches.group("title")
		book_year = books[book_title] if book_title in books else None

		output.append({
			"url": review_url,
			"datetime": review_datetime,
			"title": f"{book_title.split(':')[0]} ({book_year})" if book_year else book_title,
			"type": "goodreads",
			"details": {
				"event": "pages-read",
				"raw_title": book_title,
				"raw_year": book_year,
				"pages_read": pages_read,
				"pages_total": pages_total
			}
		})

	print(f"Finished reading XML; got {len(output)} entries. Limiting to latest 10")
	output.sort(reverse=True, key=lambda obj: datetime.datetime.fromisoformat(obj["datetime"]))
	return output


def filter_duplicates(evt_list):
	if not evt_list:
		return []

	output = []
	seen = set()
	for event in evt_list:
		title = event["title"]
		evt_type = event["details"]["event"]
		key = f"{title}-{evt_type}"
		if key in seen:
			continue
		seen.add(key)
		output.append(event)
	return output


full_rss = []
full_rss.extend(filter_duplicates(letterboxd())[:10])
full_rss.extend(filter_duplicates(wikipedia())[:10])
full_rss.extend(filter_duplicates(github())[:10])
full_rss.extend(filter_duplicates(gist())[:10])
full_rss.extend(filter_duplicates(mal())[:10])
full_rss.extend(filter_duplicates(goodreads())[:10])
full_rss.sort(reverse=True, key=lambda obj: datetime.datetime.fromisoformat(obj["datetime"]))

for obj in full_rss:
	obj["datetime"] = obj["datetime"].replace("+00:00", "Z")

MAX_EVENTS = 50
print(f"Full event list has size {len(full_rss)}; only the latest {MAX_EVENTS} will be copied")

right_now = datetime.datetime.now(tz=datetime.timezone.utc)
with open("./public/eu/rss.json", "w", encoding="utf-8") as f:
	f.write(
		json.dumps({
			"updated_at": std_datetime(right_now).replace("+00:00", "Z"),
			"data": full_rss[:MAX_EVENTS]
		})
	)
