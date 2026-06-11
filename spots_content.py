"""
Spot page content — single source of truth for the 25 spot writeups.

Used by:
  - /spots/<slug> server-rendered SEO pages (app.py)
  - the About tab spot cards on the homepage (templates/index.html via Jinja)
  - /sitemap.xml

Keys match SPOT_CONFIG names in striper_tides.py exactly. `title` is the
display name (a few differ from the config key). `blurb` copy follows site
style: no em dashes or hyphens in paragraph copy.
"""

REGION_LABELS = {
    "cape_may": "Cape May County",
    "atlantic": "Atlantic County",
    "ocean":    "Ocean County / LBI",
    "raritan":  "Raritan Bay",
    "monmouth": "Monmouth County",
}

# Display order for region groups (south to north, Cape May first)
REGION_ORDER = ["cape_may", "atlantic", "ocean", "raritan", "monmouth"]

SPOT_PAGES: dict[str, dict] = {
    # ── Cape May County — ocean / inlet ──────────────────────────────────────
    "Corsons Inlet": {
        "slug": "corsons-inlet",
        "title": "Corsons Inlet",
        "blurb": "One of the most consistent striper and bluefish inlets in Cape May County. The channel cuts hard to the north side and the rip that forms on the outgoing tide is where fish stack. Stripers and blues work the current seam aggressively from late April through June and again in October and November. The beach on the south side offers surf access to the rip from the sand. Swim shads, bucktails, and live spot work well on the drop. The inlet also produces strong fluke action in May and June on the incoming tide over the sandy channel edges.",
    },
    "Townsends Inlet": {
        "slug": "townsends-inlet",
        "title": "Townsends Inlet",
        "blurb": "A shallower, narrower inlet between Avalon and Sea Isle City that warms early in spring and holds fish longer into fall. The back bay access on both sides makes this a flexible spot depending on wind and tide. Schoolie stripers and fluke are consistent through May and June and the inlet mouth produces on the last two hours of the outgoing and the first hour of the incoming. Bucktails and paddle tails on the bottom are the standard presentation. Sea robin are plentiful here in summer which tells you the bait is always around.",
    },
    "Hereford Inlet": {
        "slug": "hereford-inlet",
        "title": "Hereford Inlet",
        "blurb": "One of the wider inlets on the Cape May County coast with powerful tidal flow and multiple channel edges to work. The rips off the lighthouse side are a landmark bass and bluefish spot during the spring run. Plugging the current seam with surface poppers and swimmers at first light in May and October is as good as it gets on the Jersey Shore. The inlet stays productive all season with weakfish and fluke joining stripers and blues through summer. Boat anglers can work the deeper cuts on the outgoing for late season bass into November.",
    },
    "Cape May Inlet": {
        "slug": "cape-may-inlet",
        "title": "Cape May Inlet",
        "blurb": "The premier inlet in South Jersey and arguably the best single striper spot in Cape May County during the spring and fall migrations. This is a major working inlet where Delaware Bay and the Atlantic meet, creating powerful tidal rips that funnel bait and hold fish for days at a time. The spring run in late April and May sees some of the biggest stripers of the year stacking in the rips. Bucktails, darters, and large swim shads on the outgoing tide at dawn and dusk are the standard approach. Weakfish, bluefish, and fluke are all caught here regularly through summer. The jetties on both sides provide surf access to the rip.",
    },
    "Cape May Point": {
        "slug": "cape-may-point",
        "title": "Cape May Point",
        "blurb": "The southernmost tip of New Jersey where the Delaware Bay current meets the Atlantic and creates the most famous striper rip in South Jersey. Fish stage here during both the spring and fall migrations making it a two season destination. The point is primarily a surf and wading spot with jetty access on the bay side. The rip forms strongest on the outgoing tide and concentrates baitfish right on the beach, bringing stripers in within casting range. Poppers and needlefish worked through the rip at dawn are the go to presentation. This is also a prime bluefish spot when bunker schools push by in October.",
    },
    # ── Cape May County — back bay ───────────────────────────────────────────
    "Grassy Sound": {
        "slug": "grassy-sound",
        "title": "Grassy Sound",
        "blurb": "A shallow, grassy back bay channel near Wildwood Crest that is one of the first spots to come alive in spring as warming water pushes into the back bay system ahead of the ocean. Flounder fishing here in late April and early May can be exceptional before ocean temps draw fish out to the inlets. Schoolie stripers work the sod bank edges on the incoming tide through May and June. The channel is narrow and the fishing is tighter than the open bay spots, which means lighter tackle and finesse presentations work better here. Bloodworms and Berkley Gulp on a fluke rig are the standard bottom approach.",
    },
    "Stone Harbor": {
        "slug": "stone-harbor-back-bay",
        "title": "Stone Harbor Back Bay",
        "blurb": "Protected back bay channels behind Stone Harbor with a mix of marsh edge structure, channel edges, and open flat areas. This system holds weakfish through summer and is one of the more consistent spots for them at dawn and dusk on the big tides around new and full moon. Flounder are also consistent from late April through June. The channel edges on the outgoing tide are where stripers work in spring. Light jig heads with soft plastics are versatile enough to cover weakfish and schoolie bass in the same presentation. The protected water makes this fishable even in a moderate southwest wind.",
    },
    "Avalon Back Bay": {
        "slug": "avalon-back-bay",
        "title": "Avalon Back Bay",
        "blurb": "Strong tidal exchange through the channels behind Avalon creates reliable current that concentrates baitfish and holds predators on both the incoming and outgoing tide. Fall stripers stack on the outgoing in October and November as water temps drop and fish begin their southward push. Schoolie bass and bluefish move through in spring as well. The back bay here is more open than the southern systems which means plugging the edges with small swimmers and paddle tails covers water efficiently. Fluke are present from May through July on the sandy bottom sections of the channel.",
    },
    "Sea Isle Back Bay": {
        "slug": "sea-isle-back-bay",
        "title": "Sea Isle Back Bay",
        "blurb": "Sheltered flats and channels behind Sea Isle City that warm ahead of the ocean and consistently produce the first flounder of the season in April and early May. Doormats push through this system during the late April and May window before moving out to the ocean inlets. The flat water makes for easy boat fishing and fish tend to concentrate on the subtle bottom transitions where sand meets soft bottom. Bloodworms and live killies are the traditional baits here. Weakfish work these flats on summer evenings and schoolie stripers use the channel edges in spring and fall.",
    },
    "Townsends Back Bay": {
        "slug": "townsends-back-bay",
        "title": "Townsends Back Bay",
        "blurb": "A productive back bay channel running behind Avalon and Sea Isle City with strong tidal flow and some of the most consistent weakfish action in the county through summer. This is one of the better spots for targeting weakfish on light tackle at dawn and dusk on the big tides. Small bucktails, curly tail grubs, and soft plastic swimmers on light jig heads are the standard approach. Flounder are also present in May and June. The channel runs close to navigable water for small boats and the structure along the marsh edges gives fish ambush points to work with the current.",
    },
    "Cape May Back Bay": {
        "slug": "cape-may-back-bay",
        "title": "Cape May Back Bay",
        "blurb": "Warm, shallow back bay water near Cape May Harbor that heats up early in spring and holds some of the best early season flounder action in the county. April flounder here can be exceptional and doormats are possible in May and June as bait concentrates in the harbor channels. Weakfish work this system through summer and the proximity to Cape May Inlet means stripers and blues push in on the tide through spring and fall. The area around the harbor entrance is particularly productive on the outgoing tide when current pulls bait out of the back bay and into the channel. Shedder crab and bucktails are worth carrying here all season.",
    },
    "The Thorofare": {
        "slug": "the-thorofare",
        "title": "The Thorofare",
        "blurb": "The main arterial channel of the Cape May back bay system with some of the strongest tidal flow and deepest structure in the back bay. Deep holes along the channel edges hold stripers through spring and fall and the current here is strong enough to put quality fish on the feed even in the middle of the tide. This is one of the better big bass spots in the back bay, especially on the outgoing tide in October and November. Bunker chunk and heavy bucktails work the holes while paddle tail swimbaits cover the current seams. Weakfish also use this channel heavily in summer. The strong current means heavier presentations than anywhere else in the back bay.",
    },
    # ── Atlantic County ──────────────────────────────────────────────────────
    "Great Egg Harbor Inlet": {
        "slug": "great-egg-harbor-inlet",
        "title": "Great Egg Harbor Inlet",
        "blurb": "A smaller inlet at the southern end of Atlantic County between Ocean City and Sea Isle City with strong tidal rips on the outgoing tide. Good striper fishing in spring and fall with the rip forming at the mouth on the drop. Fluke stack in the channel on the incoming tide from May through July. Access from the beach or by boat from the back bay side. This inlet sees less pressure than the bigger inlets to the north and south which means the fish can be a little less boat shy.",
    },
    "Somers Point Back Bay": {
        "slug": "somers-point-back-bay",
        "title": "Somers Point Back Bay",
        "blurb": "Where Great Egg Harbor Bay meets the main back bay system near Somers Point. A historically productive area for stripers and weakfish where the mouths of the tidal rivers concentrate bait and hold fish on both tides. Spring stripers work the current seams and fall bass push through heading south. Good flounder action in spring and the protected water makes it fishable in conditions that would shut down the inlets. The deeper channels near the bay mouth hold fish later into the season.",
    },
    "Atlantic City Back Bay": {
        "slug": "atlantic-city-back-bay",
        "title": "Atlantic City Back Bay",
        "blurb": "The back bay channels behind Atlantic City and the barrier islands offer a mix of tidal channels, marina structure, and open bay areas. Stripers push through in spring and fall using the channel edges and marina pilings as ambush points. Bluefish are common in the bay through summer. Weakfish and flounder work the flats from May through July. The proximity to multiple inlets means strong tidal flow through the whole system and the pilings around the casino and marina complex hold sheepshead through summer.",
    },
    "Absecon Inlet": {
        "slug": "absecon-inlet",
        "title": "Absecon Inlet",
        "blurb": "The main ocean inlet at Atlantic City. A wide, deep, high traffic inlet with serious tidal rips and one of the better big striper inlets on the central Jersey Shore during spring and fall migrations. Bluefish are consistent through summer. The jetties on both sides provide surf and rock access to the rip. Bunker schools stack in the mouth of this inlet in October and the bass fishing during those pushes can be exceptional. Heavy bucktails and large swimmers worked through the current seam are the standard approach.",
    },
    # ── Ocean County / LBI ───────────────────────────────────────────────────
    "LBI Back Bay": {
        "slug": "lbi-back-bay",
        "title": "LBI Back Bay",
        "blurb": "Little Egg Harbor and Manahawkin Bay form one of the largest back bay systems on the Jersey Shore with a massive amount of marsh edge structure, channel edges, and open water to explore. Stripers, weakfish, and flounder all use this system through the season. The western shore channels are particularly productive for spring stripers and the tidal flow through the channels behind LBI holds fish all season long. Light to medium tackle with paddle tails and soft plastics covers the most water efficiently here.",
    },
    "Barnegat Inlet": {
        "slug": "barnegat-inlet",
        "title": "Barnegat Inlet",
        "blurb": "One of the most famous striper inlets on the entire East Coast. The north jetty at Barnegat is legendary for big fall stripers from late October through December and the rip formed by the current pouring through the inlet creates world class striper fishing that draws anglers from across the region. Large plugs, bunker chunk, and heavy bucktails are the standard approach. In spring the inlet is equally productive as the migration moves north. The inlet entrance is one of the most powerful and dangerous on the coast and boat anglers need to respect the conditions here.",
    },
    "Island Beach SP": {
        "slug": "island-beach-state-park",
        "title": "Island Beach State Park",
        "blurb": "A pristine undeveloped barrier island with miles of surf fishing access and some of the best beach striper fishing in New Jersey. Stripers work the gutters and sandbars along the beachfront in spring and fall and bluefish hit poppers in the wash all summer. The south end near Barnegat Inlet is the most productive zone and fish concentrate in the rip that runs along the beach here on the outgoing tide. A buggy permit is required for oceanside beach access and the park fills fast on good weather weekends in peak season.",
    },
    # ── Raritan Bay ──────────────────────────────────────────────────────────
    "Perth Amboy": {
        "slug": "perth-amboy",
        "title": "Perth Amboy",
        "blurb": "The southwestern corner of Raritan Bay where the Raritan River meets the bay, making it a historic and productive striper spot that comes alive in spring as migrating fish push up into the river mouth. The rips and eddies around the points and shoals concentrate bass on the moving tide. Schoolies are consistent through summer and larger fish push through in spring and fall. Bottom fishing with crab and clam produces in the deeper holes. The area sees good numbers of fish in both the spring northward and fall southward migrations.",
    },
    "Keyport": {
        "slug": "keyport",
        "title": "Keyport",
        "blurb": "The Keyport area sits at the center of Raritan Bay which gives good access to migrating fish moving through in both directions. Stripers and bluefish work the bay in spring and fall and the flats off Keyport produce weakfish in summer on light tackle at dusk. The harbor and marina structure hold fish on the tide and the open bay out front is worth working on the bigger tidal swings in the spring and fall migration windows.",
    },
    "Keansburg": {
        "slug": "keansburg",
        "title": "Keansburg",
        "blurb": "The northern shore of Raritan Bay near Keansburg offers accessible shoreline fishing and boat ramp access to the open bay. Stripers move through this part of the bay in spring heading toward the rivers and in fall heading south. Bluefish are reliable here in summer and the deeper water just off the flats holds fish later into the fall season. A good option when you want open bay access without fighting the crowds at the more well known spots along the shore.",
    },
    # ── Monmouth County ──────────────────────────────────────────────────────
    "Manasquan Inlet": {
        "slug": "manasquan-inlet",
        "title": "Manasquan Inlet",
        "blurb": "One of the most productive inlets on the Jersey Shore and a major striper landmark. The rip that forms at the mouth of the inlet is legendary and the jetties on both sides provide excellent access for surf and rock fishing. Spring and fall striper runs both push fish through this inlet in big numbers and the inlet mouth is also a top bluefish spot through summer. Eels, bucktails, and large swimmers are the go to presentations. The inlet also connects to the Manasquan River which holds stripers on the spring run and is worth working with live eels at night.",
    },
    "Shark River Inlet": {
        "slug": "shark-river-inlet",
        "title": "Shark River Inlet",
        "blurb": "A smaller but productive inlet connecting Shark River to the ocean. The current rips through on the outgoing tide and concentrates bass and blues in the channel mouth. Schoolie stripers are consistent from spring through fall and the back bay behind the inlet has good weakfish and flounder action. Light tackle fishing with small jigs and soft plastics is productive throughout the season. This inlet is more approachable than Manasquan and gets less pressure on weekday tides.",
    },
    "Sandy Hook": {
        "slug": "sandy-hook",
        "title": "Sandy Hook",
        "blurb": "The northernmost point of the Jersey Shore and one of the legendary striper spots on the entire East Coast. The rip at the tip of Sandy Hook is world class striper fishing during the spring and fall migrations and big fish are common here in late April and May as the spring run peaks. The ocean side of the hook has miles of accessible beach for surf fishing and the bay side has productive back bay areas for smaller fish and weakfish. The tip of the hook and the lighthouse area are the prime zones and they fish best on the outgoing tide when the rip is at full strength.",
    },
}

# Reverse lookup: slug → SPOT_CONFIG key
SLUG_TO_NAME = {info["slug"]: name for name, info in SPOT_PAGES.items()}
