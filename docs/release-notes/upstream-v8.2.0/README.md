# Upstream release notes, v8.2.0

The `LastVersion_*.txt` files in this folder are the translated release notes that MyBot.run
published alongside its v8.2.0 release. They arrived on this fork's `master` branch as part of the
release lineage.

They sat at the repository root, where they read as project files even though nothing loads them.
The bot's update check (`COCBot/functions/Other/CheckVersion.au3`) reads the GitHub releases API and
parses the response — it never opens these files. They are kept here for reference and attribution
rather than because the code needs them.

Some languages appear twice under both an English and a native name (`LastVersion_Turkish.txt` and
`LastVersion_Türkçe.txt`, for example). That duplication is how upstream shipped them and has been
left alone.
