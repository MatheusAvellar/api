# -*- coding: utf-8 -*-
import datetime
import re
import requests
import json
from bs4 import BeautifulSoup

def get_text(element: BeautifulSoup | None):
	if element is not None:
		return element.get_text().strip()
	return ""


def get_html(url, headers=None):
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
	return BeautifulSoup(res.text, "html.parser")


def std_datetime(date):
	return (
		date
		.astimezone(tz=datetime.timezone.utc)
		.isoformat()
	)


def lastfm():
	custom_ua = "Mozilla/5.0 (Windows NT 10.0; selfrss@avl.la) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"
	soup = get_html(
		"https://www.last.fm/user/MatheusAvellar/partial/recenttracks?ajax=1",
		headers={ "User-Agent": custom_ua }
	)

	output = []
	if soup is None:
		print(f"Failed reading HTML response")
	else:
		for row in soup.find("tbody").find_all("tr"):
			if len(row.find_all("td")) <= 2:
				continue

			cover_url = row.find("img").get("src")

			song_title = get_text(row.find("td", attrs={ "class": "chartlist-name" }))
			artist_name = get_text(row.find("td", attrs={ "class": "chartlist-artist" }))

			timestamp_wrapper = row.find("td", attrs={ "class": "chartlist-timestamp" })
			timestamp_span = timestamp_wrapper.find("span")

			dt = None
			# Something like "Sunday 4 Jan 2026, 9:11pm"
			dt_text = timestamp_span.get("title")
			if dt_text:
				print(f"Has listen datetime: {dt_text}")
				dt = datetime.datetime.strptime(dt_text, "%A %d %b %Y, %I:%M%p")
			else:
				print(f"No listen datetime; using right now")
				dt = datetime.datetime.now().replace(microsecond=0)

			# If this event is older than a month, ignore it
			if dt < (datetime.datetime.now() - datetime.timedelta(days=30)):
				continue

			listen_datetime = std_datetime(dt)

			output.append({
				"url": "",
				"artist": artist_name,
				"title": song_title,
				"datetime": listen_datetime,
				"cover_url": cover_url
			})

	print(f"Finished reading HTML; got {len(output)} entries. Limiting to latest 10")
	output.sort(reverse=True, key=lambda obj: datetime.datetime.fromisoformat(obj["datetime"]))
	return output


full_rss = []
full_rss.extend(lastfm()[:10])
# full_rss.sort(reverse=True, key=lambda obj: datetime.datetime.fromisoformat(obj["datetime"]))

for obj in full_rss:
	obj["datetime"] = obj["datetime"].replace("+00:00", "Z")

MAX_EVENTS = 50
print(f"Full event list has size {len(full_rss)}; only the latest {MAX_EVENTS} will be copied")

right_now = datetime.datetime.now(tz=datetime.timezone.utc)
with open("./public/eu/lastfm.json", "w", encoding="utf-8") as f:
	f.write(
		json.dumps({
			"updated_at": std_datetime(right_now).replace("+00:00", "Z"),
			"data": full_rss[:MAX_EVENTS]
		})
	)
