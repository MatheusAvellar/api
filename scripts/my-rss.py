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


def get_xml(url):
	print(f"Sending GET to '{url}'")
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
	for url in urls:
		soup = get_xml(url)
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
	urls = [
		"https://github.com/MatheusAvellar.atom",
		"https://gist.github.com/MatheusAvellar.atom",
	]
	output = []
	for url in urls:
		soup = get_xml(url)
		if soup is None:
			continue

		for entry in soup.find_all("entry"):
			# <entry>
			# 	<id>tag:github.com,2008:PullRequestEvent/52789137971</id>
			# 	<published>2025-07-31T14:32:52Z</published>
			# 	<updated>2025-07-31T14:32:52Z</updated>
			# 	<link type="text/html" rel="alternate" href="https://github.com/prefeitura-rio/pipelines_rj_sms/pull/432"/>
			# 	<title type="html">MatheusAvellar opened a pull request in prefeitura-rio/pipelines_rj_sms</title>
			# 	<author>
			# 		<name>MatheusAvellar</name>
			# 		<uri>https://github.com/MatheusAvellar</uri>
			# 	</author>
			# 	<media:thumbnail height="30" width="30" url="https://avatars.githubusercontent.com/u/1719996?s=30&amp;v=4"/>
			# 	<content type="html">...</content>
			# </entry>
			event_url = entry.find("link", { "rel": "alternate" }).get("href")

			def get_title_parts(s):
				# Push to branch
				if s.startswith("pushed to"):
					return ( "Pushed to branch", s.split("pushed to")[1].strip() )
				# Pull request
				if s.startswith("opened a pull"):
					return ( "Pull request", s.split("pull request in")[1].strip() )
				# Create repository
				if s.startswith("created a repository"):
					return ( "Created repository", s.split("repository")[1].strip() )
				# Create branch
				if s.startswith("created a branch"):
					return ( "Created branch", s.split("created a branch")[1].strip() )
				# Delete branch
				if s.startswith("deleted branch"):
					return ( "Deleted branch", s.split("deleted branch")[1].strip() )
				# Made repository public
				m = re.match(r"^made ([^\s/]+/[^\s/]+) public", s)
				if m is not None:
					repo = m.group(1)
					return ( "Made public", repo )
				# Star repository
				if s.startswith("starred"):
					return ( "Starred repository", s.split("starred")[1].strip() )
				# Close issue
				if s.startswith("closed an issue"):
					return ( "Closed an issue", s.split("closed an issue in")[1].strip() )

				# Gist titles, unknown events
				# Make sure first letter is capitalized
				# (.capitalize() lowercases all other letters)
				return ((s[:1].upper() + s[1:]), "")

			event_description, event_details = get_title_parts(
				get_text(entry.find("title")).removeprefix("MatheusAvellar ").strip()
			)

			branch = ""
			repository = None
			if " in " in event_details:
				(branch, repository) = event_details.split(" in ")
			elif " at " in event_details:
				(branch, repository) = event_details.split(" at ")
			else:
				repository = event_details

			# Too many of these, let's just ignore them
			if event_description == "Pushed to branch":
				continue
			# This is a duplicate of "created repository" (in 99.99% of cases)
			if event_description == "Created branch" and branch == "main":
				continue

			updated = get_text(entry.find("updated"))
			dt = datetime.datetime.strptime(updated, "%Y-%m-%dT%H:%M:%S%z")
			# If this event is older than a month, ignore it
			if dt < (datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(days=30)):
				continue
			event_datetime = std_datetime(dt)
			event_type = (
				get_text(entry.find("id"))
				.removeprefix("tag:github.com,2008:")
				.removeprefix("tag:gist.github.com,2008:")
				.split("/")[0]
			)

			gh_prefix = url.removeprefix("https://").split(".")[0]
			output.append({
				"url": event_url,
				"datetime": event_datetime,
				"title": repository or event_description,
				"type": "github",
				"details": {
					"event": event_type,
					"kind": gh_prefix,
					"description": event_description,
					"branch": branch,
					"repository": repository
				}
			})
	print(f"Finished reading XML; got {len(output)} entries. Limiting to latest 10")
	output.sort(reverse=True, key=lambda obj: datetime.datetime.fromisoformat(obj["datetime"]))
	return output


# Flickr:
# https://www.flickr.com/services/feeds/photos_public.gne?id=202939403@N02


def filter_duplicates(evt_list):
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
full_rss.extend(filter_duplicates(mal())[:10])
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
