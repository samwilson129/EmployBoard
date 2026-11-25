"""Discover real public ATS boards for a curated list of companies.

This maintenance tool only uses the documented public posting APIs:

* Greenhouse  https://boards-api.greenhouse.io/v1/boards/{board}/jobs
* Lever       https://api.lever.co/v0/postings/{board}?mode=json
* Ashby       https://api.ashbyhq.com/posting-api/job-board/{board}
* SmartRecruiters https://api.smartrecruiters.com/v1/companies/{id}/postings
* Recruitee   https://{company}.recruitee.com/api/offers
* Workable    https://apply.workable.com/api/v1/widget/accounts/{company}
* Personio    https://{company}.jobs.personio.de/xml?language=en
* Teamtailor  https://{company}.teamtailor.com/jobs.rss

A board is only reported as verified when the provider returns live postings
and the provider-reported company name matches the candidate. Nothing is
fabricated: boards that do not exist are simply absent from the output.

Usage (from backend/):

    python scripts/discover_boards.py --output scripts/board_discovery.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

USER_AGENT = "EmployBoard/1.0 (public job aggregation; board discovery)"
TIMEOUT = httpx.Timeout(45.0, connect=15.0)
CONCURRENCY = 8

# name | slug | domain
CANDIDATES_RAW = """
Stripe | stripe | stripe.com
Airbnb | airbnb | airbnb.com
Coinbase | coinbase | coinbase.com
DoorDash | doordash | doordash.com
Instacart | instacart | instacart.com
Reddit | reddit | reddit.com
Discord | discord | discord.com
Figma | figma | figma.com
Robinhood | robinhood | robinhood.com
Databricks | databricks | databricks.com
Datadog | datadog | datadoghq.com
Cloudflare | cloudflare | cloudflare.com
MongoDB | mongodb | mongodb.com
Elastic | elastic | elastic.co
HashiCorp | hashicorp | hashicorp.com
Confluent | confluent | confluent.io
Vercel | vercel | vercel.com
Replit | replit | replit.com
Ramp | ramp | ramp.com
Brex | brex | brex.com
Gusto | gusto | gusto.com
Rippling | rippling | rippling.com
Deel | deel | deel.com
Remote | remote | remote.com
Flexport | flexport | flexport.com
Affirm | affirm | affirm.com
Chime | chime | chime.com
SoFi | sofi | sofi.com
Plaid | plaid | plaid.com
Squarespace | squarespace | squarespace.com
Wix | wix | wix.com
Twilio | twilio | twilio.com
Asana | asana | asana.com
Pinterest | pinterest | pinterest.com
Dropbox | dropbox | dropbox.com
Lyft | lyft | lyft.com
Anthropic | anthropic | anthropic.com
Scale AI | scaleai | scale.com
Cohere | cohere | cohere.com
Grammarly | grammarly | grammarly.com
Duolingo | duolingo | duolingo.com
Calendly | calendly | calendly.com
Airtable | airtable | airtable.com
Zapier | zapier | zapier.com
Webflow | webflow | webflow.com
Framer | framer | framer.com
Retool | retool | retool.com
Netlify | netlify | netlify.com
Snyk | snyk | snyk.io
Sentry | sentry | sentry.io
1Password | 1password | 1password.com
Tailscale | tailscale | tailscale.com
Postman | postman | postman.com
Canva | canva | canva.com
Miro | miro | miro.com
Loom | loom | loom.com
Amplitude | amplitude | amplitude.com
Segment | segment | segment.com
Gong | gong | gong.io
Outreach | outreach | outreach.io
Intercom | intercom | intercom.com
Zendesk | zendesk | zendesk.com
Atlassian | atlassian | atlassian.com
Shopify | shopify | shopify.com
Block | block | block.xyz
Uber | uber | uber.com
Snap | snap | snap.com
Roblox | roblox | roblox.com
Twitch | twitch | twitch.tv
Quora | quora | quora.com
Medium | medium | medium.com
Substack | substack | substack.com
Patreon | patreon | patreon.com
Kickstarter | kickstarter | kickstarter.com
Eventbrite | eventbrite | eventbrite.com
Coursera | coursera | coursera.org
Udemy | udemy | udemy.com
Khan Academy | khanacademy | khanacademy.org
Quizlet | quizlet | quizlet.com
Chegg | chegg | chegg.com
Wayfair | wayfair | wayfair.com
Etsy | etsy | etsy.com
Poshmark | poshmark | poshmark.com
StockX | stockx | stockx.com
GOAT | goat | goat.com
Farfetch | farfetch | farfetch.com
Revolve | revolve | revolve.com
Glossier | glossier | glossier.com
Warby Parker | warbyparker | warbyparker.com
Allbirds | allbirds | allbirds.com
Casper | casper | casper.com
Away | away | awaytravel.com
Peloton | peloton | onepeloton.com
WHOOP | whoop | whoop.com
Oura | oura | ouraring.com
Calm | calm | calm.com
Headspace | headspace | headspace.com
BetterHelp | betterhelp | betterhelp.com
Teladoc | teladoc | teladochealth.com
Hims & Hers | hims | hims.com
Oscar Health | oscar | hioscar.com
Clover Health | cloverhealth | cloverhealth.com
Devoted Health | devotedhealth | devotedhealth.com
Cityblock Health | cityblock | cityblockhealth.com
Carbon Health | carbonhealth | carbonhealth.com
One Medical | onemedical | onemedical.com
Zocdoc | zocdoc | zocdoc.com
Doximity | doximity | doximity.com
GoodRx | goodrx | goodrx.com
Flatiron Health | flatironhealth | flatiron.com
Tempus | tempus | tempus.com
Recursion | recursion | recursionpharma.com
Benchling | benchling | benchling.com
Ginkgo Bioworks | ginkgobioworks | ginkgobioworks.com
10x Genomics | 10xgenomics | 10xgenomics.com
Illumina | illumina | illumina.com
Virta Health | virtahealth | virtahealth.com
Omada Health | omadahealth | omadahealth.com
Lyra Health | lyrahealth | lyrahealth.com
Spring Health | springhealth | springhealth.com
Modern Health | modernhealth | modernhealth.com
Talkspace | talkspace | talkspace.com
SonderMind | sondermind | sondermind.com
Mercury | mercury | mercury.com
Checkout.com | checkoutcom | checkout.com
Adyen | adyen | adyen.com
Klarna | klarna | klarna.com
Wise | wise | wise.com
Revolut | revolut | revolut.com
Monzo | monzo | monzo.com
N26 | n26 | n26.com
Current | current | current.com
Varo | varo | varo.com
Marqeta | marqeta | marqeta.com
Bill.com | billcom | bill.com
Melio | melio | melio.com
Tipalti | tipalti | tipalti.com
Justworks | justworks | justworks.com
Oyster | oyster | oysterhr.com
Papaya Global | papayaglobal | papayaglobal.com
Pilot | pilot | pilot.com
Bench | bench | bench.co
Perplexity | perplexity | perplexity.ai
Character.AI | character | character.ai
Adept | adept | adept.ai
Inflection AI | inflection | inflection.ai
Stability AI | stabilityai | stability.ai
Runway | runway | runwayml.com
ElevenLabs | elevenlabs | elevenlabs.io
Synthesia | synthesia | synthesia.io
HeyGen | heygen | heygen.com
Jasper | jasper | jasper.ai
Writer | writer | writer.com
Glean | glean | glean.com
Moveworks | moveworks | moveworks.com
Ada | ada | ada.cx
Decagon | decagon | decagon.ai
Sierra | sierra | sierra.ai
Cresta | cresta | cresta.ai
ASAPP | asapp | asapp.com
Cognition | cognition | cognition.ai
Poolside | poolside | poolside.ai
Together AI | together | together.ai
Fireworks AI | fireworksai | fireworks.ai
Anyscale | anyscale | anyscale.com
Modal | modal | modal.com
Replicate | replicate | replicate.com
Hugging Face | huggingface | huggingface.co
Weights & Biases | weightsandbiases | wandb.ai
LangChain | langchain | langchain.com
Pinecone | pinecone | pinecone.io
Weaviate | weaviate | weaviate.io
Qdrant | qdrant | qdrant.tech
Chroma | chroma | trychroma.com
Neon | neon | neon.tech
PlanetScale | planetscale | planetscale.com
Cockroach Labs | cockroachlabs | cockroachlabs.com
Temporal | temporal | temporal.io
Dagger | dagger | dagger.io
Railway | railway | railway.app
Render | render | render.com
Fly.io | fly | fly.io
Warp | warp | warp.dev
Raycast | raycast | raycast.com
Height | height | height.app
Linear | linear | linear.app
Cal.com | cal | cal.com
Resend | resend | resend.com
Clerk | clerk | clerk.com
WorkOS | workos | workos.com
Stytch | stytch | stytch.com
Supabase | supabase | supabase.com
PostHog | posthog | posthog.com
Vanta | vanta | vanta.com
Drata | drata | drata.com
Secureframe | secureframe | secureframe.com
Clay | clay | clay.com
Grafana | grafana | grafana.com
ClickHouse | clickhouse | clickhouse.com
Fivetran | fivetran | fivetran.com
Airbyte | airbyte | airbyte.com
dbt Labs | dbtlabs | dbtlabs.com
Prefect | prefect | prefect.io
Dagster | dagster | dagster.io
Okta | okta | okta.com
Auth0 | auth0 | auth0.com
Bitwarden | bitwarden | bitwarden.com
Dashlane | dashlane | dashlane.com
CyberArk | cyberark | cyberark.com
SailPoint | sailpoint | sailpoint.com
CrowdStrike | crowdstrike | crowdstrike.com
SentinelOne | sentinelone | sentinelone.com
Rapid7 | rapid7 | rapid7.com
Tenable | tenable | tenable.com
Qualys | qualys | qualys.com
Recorded Future | recordedfuture | recordedfuture.com
KnowBe4 | knowbe4 | knowbe4.com
Proofpoint | proofpoint | proofpoint.com
Abnormal Security | abnormalsecurity | abnormalsecurity.io
Material Security | materialsecurity | material.security
Palo Alto Networks | paloaltonetworks | paloaltonetworks.com
Akamai | akamai | akamai.com
Fastly | fastly | fastly.com
Kong | kong | konghq.com
Appsmith | appsmith | appsmith.com
Budibase | budibase | budibase.com
Prisma | prisma | prisma.io
Hasura | hasura | hasura.io
Redis | redis | redis.com
Couchbase | couchbase | couchbase.com
Neo4j | neo4j | neo4j.com
Yugabyte | yugabyte | yugabyte.com
Domino's | dominos | dominos.com
Grab | grab | grab.com
Delivery Hero | deliveryhero | deliveryhero.com
Continental | continental | continental.com
Ubisoft | ubisoft | ubisoft.com
Skyscanner | skyscanner | skyscanner.net
Aviva | aviva | aviva.com
Vodafone | vodafone | vodafone.com
Tesco | tesco | tesco.com
Aldi | aldi | aldi.com
Lidl | lidl | lidl.com
PepsiCo | pepsico | pepsico.com
Sanofi | sanofi | sanofi.com
Philips | philips | philips.com
Siemens | siemens | siemens.com
Dell | dell | dell.com
Intel | intel | intel.com
Cisco | cisco | cisco.com
Oracle | oracle | oracle.com
IBM | ibm | ibm.com
Accenture | accenture | accenture.com
Deloitte | deloitte | deloitte.com
PwC | pwc | pwc.com
EY | ey | ey.com
KPMG | kpmg | kpmg.com
Unilever | unilever | unilever.com
Nestle | nestle | nestle.com
Coca-Cola | cocacola | coca-cola.com
Pepsi | pepsi | pepsi.com
Nike | nike | nike.com
Adidas | adidas | adidas.com
Inditex | inditex | inditex.com
H&M | hm | hm.com
IKEA | ikea | ikea.com
Walmart | walmart | walmart.com
Target | target | target.com
Costco | costco | costco.com
Lowe's | lowes | lowes.com
Home Depot | homedepot | homedepot.com
Starbucks | starbucks | starbucks.com
Burger King | burgerking | burgerking.com
KFC | kfc | kfc.com
Subway | subway | subway.com
Pizza Hut | pizzahut | pizzahut.com
McDonald's | mcdonalds | mcdonalds.com
Booking.com | booking | booking.com
Expedia | expedia | expedia.com
TripAdvisor | tripadvisor | tripadvisor.com
Agoda | agoda | agoda.com
Gojek | gojek | gojek.com
Shopee | shopee | shopee.com
Lazada | lazada | lazada.com
Rakuten | rakuten | rakuten.com
Coupang | coupang | coupang.com
Zalando | zalando | zalando.com
Otto | otto | otto.de
MediaMarkt | mediamarkt | mediamarkt.com
Rewe | rewe | rewe.de
Edeka | edeka | edeka.de
Bayer | bayer | bayer.com
BASF | basf | basf.com
BMW | bmw | bmw.com
Mercedes-Benz | mercedesbenz | mercedes-benz.com
Volkswagen | volkswagen | volkswagen.com
Audi | audi | audi.com
Porsche | porsche | porsche.com
ZF | zf | zf.com
Siemens Healthineers | siemenshealthineers | siemens-healthineers.com
"""

# Second-pass candidates. These are additional real companies selected because
# their public careers pages are commonly hosted by one of the supported ATS
# providers. The provider feed and reported company identity remain the source
# of truth; candidates that do not resolve are omitted.
EXTRA_CANDIDATES_RAW = """
GitHub | github | github.com
Palantir | palantir | palantir.com
Zoom | zoom | zoom.us
Roku | roku | roku.com
Electronic Arts | ea | ea.com
Activision Blizzard | activisionblizzard | activisionblizzard.com
King | king | king.com
Unity | unity | unity.com
Epic Games | epicgames | epicgames.com
Niantic | niantic | nianticlabs.com
Squarespace | squarespace | squarespace.com
Box | box | box.com
Dropbox | dropbox | dropbox.com
Egnyte | egnyte | egnyte.com
DocuSign | docusign | docusign.com
OneTrust | onetrust | onetrust.com
Procore | procore | procore.com
Smartsheet | smartsheet | smartsheet.com
Monday.com | monday | monday.com
ClickUp | clickup | clickup.com
Mural | mural | mural.co
Lucid Software | lucidsoftware | lucid.co
Khan Academy | khanacademy | khanacademy.org
Chegg | chegg | chegg.com
MasterClass | masterclass | masterclass.com
Skillshare | skillshare | skillshare.com
Udacity | udacity | udacity.com
Codecademy | codecademy | codecademy.com
Coursera | coursera | coursera.org
Springboard | springboard | springboard.com
Handshake | handshake | joinhandshake.com
Guild Education | guild | guildeducation.com
Faire | faire | faire.com
Thrasio | thrasio | thrasio.com
Instacart | instacart | instacart.com
Postmates | postmates | postmates.com
Gopuff | gopuff | gopuff.com
Grubhub | grubhub | grubhub.com
Toast | toast | toasttab.com
ChowNow | chownow | chownow.com
Opendoor | opendoor | opendoor.com
Compass | compass | compass.com
Redfin | redfin | redfin.com
Zillow | zillow | zillow.com
Rocket Mortgage | rocket | rocketmortgage.com
Lemonade | lemonade | lemonade.com
Root Insurance | rootinsurance | root.com
Hippo Insurance | hippo | hippo.com
Marshmallow | marshmallow | marshmallow.com
SpotOn | spoton | spoton.com
Toast | toast | toasttab.com
Nuro | nuro | nuro.ai
Aurora Innovation | aurora | aurora.tech
Waymo | waymo | waymo.com
Zoox | zoox | zoox.com
Rivian | rivian | rivian.com
Lucid Motors | lucidmotors | lucidmotors.com
Polestar | polestar | polestar.com
Flex | flex | flex.com
GoPro | gopro | gopro.com
Sonos | sonos | sonos.com
Peloton | peloton | onepeloton.com
Whoop | whoop | whoop.com
Eight Sleep | eightsleep | eightsleep.com
Klaviyo | klaviyo | klaviyo.com
Braze | braze | braze.com
Iterable | iterable | iterable.com
Customer.io | customerio | customer.io
Drift | drift | drift.com
HubSpot | hubspot | hubspot.com
Salesforce | salesforce | salesforce.com
ServiceNow | servicenow | servicenow.com
Workday | workday | workday.com
Freshworks | freshworks | freshworks.com
Intercom | intercom | intercom.com
Pendo | pendo | pendo.io
LaunchDarkly | launchdarkly | launchdarkly.com
New Relic | newrelic | newrelic.com
PagerDuty | pagerduty | pagerduty.com
Samsara | samsara | samsara.com
Qualtrics | qualtrics | qualtrics.com
Medallia | medallia | medallia.com
Five9 | five9 | five9.com
Genesys | genesys | genesys.com
Motive | motive | gomotive.com
Highspot | highspot | highspot.com
Seismic | seismic | seismic.com
Gong | gong | gong.io
Salesloft | salesloft | salesloft.com
Outreach | outreach | outreach.io
Clari | clari | clari.com
Apollo.io | apollo | apollo.io
ZoomInfo | zoominfo | zoominfo.com
Ramp | ramp | ramp.com
Airwallex | airwallex | airwallex.com
Brex | brex | brex.com
Navan | navan | navan.com
TravelPerk | travelperk | travelperk.com
Papaya Global | papayaglobal | papayaglobal.com
Remote | remote | remote.com
Deel | deel | deel.com
Multiplier | multiplier | multiplier.com
Rippling | rippling | rippling.com
Justworks | justworks | justworks.com
Gusto | gusto | gusto.com
TriNet | trinet | trinet.com
Zenefits | zenefits | zenefits.com
Lattice | lattice | lattice.com
Culture Amp | cultureamp | cultureamp.com
15Five | 15five | 15five.com
BetterUp | betterup | betterup.com
Modern Health | modernhealth | modernhealth.com
Spring Health | springhealth | springhealth.com
Headspace | headspace | headspace.com
Hims & Hers | hims | hims.com
Ro | ro | ro.co
Thirty Madison | thirtymadison | thirtymadison.com
Included Health | includedhealth | includedhealth.com
Color Health | color | color.com
Komodo Health | komodohealth | komodohealth.com
Flatiron Health | flatironhealth | flatiron.com
Benchling | benchling | benchling.com
Recursion | recursion | recursionpharma.com
Insitro | insitro | insitro.com
Tempus | tempus | tempus.com
Grail | grail | grail.com
Alloy Therapeutics | alloytx | alloytx.com
Kaiser Permanente | kaiserpermanente | kp.org
Elevance Health | elevance | elevancehealth.com
CVS Health | cvshealth | cvshealth.com
UnitedHealth Group | uhg | uhg.com
Mayo Clinic | mayoclinic | mayoclinic.org
Y Combinator | ycombinator | ycombinator.com
Andreessen Horowitz | a16z | a16z.com
Sequoia Capital | sequoiacapital | sequoiacap.com
Insight Partners | insightpartners | insightpartners.com
Tiger Global | tigerglobal | tigerglobal.com
Carta | carta | carta.com
AngelList | angellist | angellist.com
Plaid | plaid | plaid.com
Marqeta | marqeta | marqeta.com
Chime | chime | chime.com
Current | current | current.com
Varo Bank | varobank | varomoney.com
SoFi | sofi | sofi.com
LendingClub | lendingclub | lendingclub.com
Upgrade | upgrade | upgrade.com
Figure | figure | figure.com
Affirm | affirm | affirm.com
Klarna | klarna | klarna.com
Checkout.com | checkoutcom | checkout.com
Adyen | adyen | adyen.com
PayPal | paypal | paypal.com
Block | block | block.xyz
Wise | wise | wise.com
Revolut | revolut | revolut.com
Monzo | monzo | monzo.com
Nubank | nubank | nubank.com
Mercado Libre | mercadolibre | mercadolibre.com
Rappi | rappi | rappi.com
Kavak | kavak | kavak.com
OLX | olx | olx.com
Vinted | vinted | vinted.com
Depop | depop | depop.com
The RealReal | therealreal | therealreal.com
Chewy | chewy | chewy.com
Petco | petco | petco.com
Warby Parker | warbyparker | warbyparker.com
Allbirds | allbirds | allbirds.com
Everlane | everlane | everlane.com
Rent the Runway | renttherunway | renttherunway.com
Stitch Fix | stitchfix | stitchfix.com
The Farmer's Dog | farmersdog | thefarmersdog.com
Maven Clinic | mavenclinic | mavenclinic.com
Eight Sleep | eightsleep | eightsleep.com
Calm | calm | calm.com
BetterHelp | betterhelp | betterhelp.com
Talkspace | talkspace | talkspace.com
Lyra Health | lyrahealth | lyrahealth.com
Cityblock Health | cityblock | cityblockhealth.com
Carbon Health | carbonhealth | carbonhealth.com
One Medical | onemedical | onemedical.com
Tia | tia | asktia.com
Forward | forward | goforward.com
Roivant Sciences | roivant | roivant.com
Oscar Health | oscar | hioscar.com
Duolingo | duolingo | duolingo.com
Rosetta Stone | rosettastone | rosettastone.com
Quizlet | quizlet | quizlet.com
Remind | remind | remind.com
Outschool | outschool | outschool.com
Newsela | newsela | newsela.com
Instructure | instructure | instructure.com
Pearson | pearson | pearson.com
McGraw Hill | mcgrawhill | mheducation.com
Etsy | etsy | etsy.com
eBay | ebay | ebay.com
Poshmark | poshmark | poshmark.com
StockX | stockx | stockx.com
GOAT | goat | goat.com
Farfetch | farfetch | farfetch.com
The Knot Worldwide | theknot | theknot.com
Eventbrite | eventbrite | eventbrite.com
Fever | fever | feverup.com
ClassPass | classpass | classpass.com
Mindbody | mindbody | mindbodyonline.com
Patreon | patreon | patreon.com
Substack | substack | substack.com
Medium | medium | medium.com
Quora | quora | quora.com
Twitch | twitch | twitch.tv
Vimeo | vimeo | vimeo.com
Dailymotion | dailymotion | dailymotion.com
BuzzFeed | buzzfeed | buzzfeed.com
The Athletic | theathletic | theathletic.com
Vox Media | voxmedia | voxmedia.com
Condé Nast | condenast | condenast.com
Hearst | hearst | hearst.com
Warner Music Group | warnermusicgroup | wmg.com
Universal Music Group | universalmusicgroup | universalmusic.com
Live Nation | livenation | livenation.com
ProSiebenSat.1 | prosiebensat1 | prosiebensat1.com
Delivery Hero | deliveryhero | deliveryhero.com
HelloFresh | hellofresh | hellofresh.com
Gopuff | gopuff | gopuff.com
Getir | getir | getir.com
Bolt | bolt | bolt.eu
FreeNow | freenow | free-now.com
Cabify | cabify | cabify.com
Grab | grab | grab.com
Sea Group | sea | sea.com
Lazada | lazada | lazada.com
Rakuten | rakuten | rakuten.com
Mercari | mercari | mercari.com
Line | line | line.me
Naver | naver | naver.com
Kakao | kakao | kakao.com
Samsung | samsung | samsung.com
LG Electronics | lg | lge.com
Panasonic | panasonic | panasonic.com
Philips | philips | philips.com
Siemens | siemens | siemens.com
ABB | abb | abb.com
Schneider Electric | schneider | se.com
Honeywell | honeywell | honeywell.com
Carrier | carrier | carrier.com
Cummins | cummins | cummins.com
John Deere | johndeere | johndeere.com
Deere & Company | deerCompany | deere.com
Ford | ford | ford.com
General Motors | gm | gm.com
Toyota | toyota | toyota.com
Honda | honda | honda.com
Hyundai | hyundai | hyundai.com
Volvo | volvo | volvocars.com
Jaguar Land Rover | jlr | jlr.com
Boeing | boeing | boeing.com
Airbus | airbus | airbus.com
Lockheed Martin | lockheedmartin | lockheedmartin.com
Northrop Grumman | northropgrumman | northropgrumman.com
Raytheon | raytheon | rtx.com
General Dynamics | gd | gd.com
SpaceX | spacex | spacex.com
Rocket Lab | rocketlab | rocketlabusa.com
Relativity Space | relativityspace | relativityspace.com
Anduril | anduril | anduril.com
Shield AI | shieldai | shield.ai
Scale AI | scaleai | scale.com
Skydio | skydio | skydio.com
Zipline | zipline | flyzipline.com
Veeam | veeam | veeam.com
Darktrace | darktrace | darktrace.com
Wiz | wiz | wiz.io
Snyk | snyk | snyk.io
Tenable | tenable | tenable.com
CrowdStrike | crowdstrike | crowdstrike.com
SentinelOne | sentinelone | sentinelone.com
Mandiant | mandiant | mandiant.com
Cloudinary | cloudinary | cloudinary.com
Algolia | algolia | algolia.com
Meilisearch | meilisearch | meilisearch.com
Cockroach Labs | cockroachlabs | cockroachlabs.com
PlanetScale | planetscale | planetscale.com
Neon | neon | neon.tech
Turso | turso | turso.tech
Convex | convex | convex.dev
Hasura | hasura | hasura.io
Appwrite | appwrite | appwrite.io
Directus | directus | directus.io
Strapi | strapi | strapi.io
Contentful | contentful | contentful.com
Sanity | sanity | sanity.io
Prismic | prismic | prismic.io
Builder.io | builder | builder.io
Unbounce | unbounce | unbounce.com
Vercel | vercel | vercel.com
Netlify | netlify | netlify.com
Fly.io | fly | fly.io
Railway | railway | railway.app
Render | render | render.com
Heroku | heroku | heroku.com
DigitalOcean | digitalocean | digitalocean.com
Linode | linode | linode.com
Vultr | vultr | vultr.com
OVHcloud | ovhcloud | ovhcloud.com
Hetzner | hetzner | hetzner.com
Canonical | canonical | canonical.com
Mozilla | mozilla | mozilla.org
Automattic | automattic | automattic.com
WordPress.com | wordpress | wordpress.com
Atlassian | atlassian | atlassian.com
Confluent | confluent | confluent.io
HashiCorp | hashicorp | hashicorp.com
Cockroach Labs | cockroachlabs | cockroachlabs.com
Flink | flink | flink.apache.org
Elastic Path | elasticpath | elasticpath.com
Meltano | meltano | meltano.com
dbt Labs | dbtlabs | dbtlabs.com
Prefect | prefect | prefect.io
Dagster | dagster | dagster.io
Airbyte | airbyte | airbyte.com
Fivetran | fivetran | fivetran.com
Monte Carlo Data | montecarlodata | montecarlodata.com
Starburst | starburst | starburstdata.com
SingleStore | singlestore | singlestore.com
Materialize | materialize | materialize.com
MotherDuck | motherduck | motherduck.com
Hex | hex | hex.tech
Hex Technologies | hextechnologies | hex.tech
Sigma Computing | sigmacomputing | sigmacomputing.com
ThoughtSpot | thoughtspot | thoughtspot.com
Looker | looker | looker.com
Mode Analytics | modeanalytics | modeanalytics.com
Dataiku | dataiku | dataiku.com
DataRobot | datarobot | datarobot.com
H2O.ai | h2oai | h2o.ai
Weights & Biases | weightsandbiases | wandb.ai
Hugging Face | huggingface | huggingface.co
Replicate | replicate | replicate.com
Together AI | together | together.ai
Fireworks AI | fireworksai | fireworks.ai
Anyscale | anyscale | anyscale.com
Modal | modal | modal.com
Runway | runway | runwayml.com
ElevenLabs | elevenlabs | elevenlabs.io
Synthesia | synthesia | synthesia.io
Character.AI | character | character.ai
Inflection AI | inflection | inflection.ai
Stability AI | stabilityai | stability.ai
Mistral AI | mistral | mistral.ai
AI21 Labs | ai21 | ai21.com
Cohere | cohere | cohere.com
Hugging Face | huggingface | huggingface.co
Pinecone | pinecone | pinecone.io
Weaviate | weaviate | weaviate.io
Qdrant | qdrant | qdrant.tech
LangChain | langchain | langchain.com
LlamaIndex | llamaindex | llamaindex.ai
OpenRouter | openrouter | openrouter.ai
Perplexity | perplexity | perplexity.ai
Cursor | cursor | cursor.com
Replit | replit | replit.com
Sourcegraph | sourcegraph | sourcegraph.com
GitKraken | gitkraken | gitkraken.com
Linear | linear | linear.app
Height | height | height.app
Cal.com | cal | cal.com
Clerk | clerk | clerk.com
WorkOS | workos | workos.com
Stytch | stytch | stytch.com
Auth0 | auth0 | auth0.com
Okta | okta | okta.com
Vanta | vanta | vanta.com
Drata | drata | drata.com
Secureframe | secureframe | secureframe.com
Kintent | kintent | kintent.com
Thoropass | thoropass | thoropass.com
Secureframe | secureframe | secureframe.com
Drift | drift | drift.com
Ada | ada | ada.cx
Moveworks | moveworks | moveworks.com
Glean | glean | glean.com
Sierra | sierra | sierra.ai
Cognition | cognition | cognition.ai
Poolside | poolside | poolside.ai
Decagon | decagon | decagon.ai
Sierra AI | sierraai | sierra.ai
Writer | writer | writer.com
Jasper | jasper | jasper.ai
Copy.ai | copyai | copy.ai
Typeface | typeface | typeface.ai
Eight Sleep | eightsleep | eightsleep.com
Oura | oura | ouraring.com
WHOOP | whoop | whoop.com
Strava | strava | strava.com
Komoot | komoot | komoot.com
AllTrails | alltrails | alltrails.com
ClassPass | classpass | classpass.com
Noom | noom | noom.com
WeightWatchers | weightwatchers | weightwatchers.com
Hinge Health | hingehealth | hingehealth.com
Kindbody | kindbody | kindbody.com
Tandem Diabetes | tandemdiabetes | tandemdiabetes.com
Insulet | insulet | insulet.com
Dexcom | dexcom | dexcom.com
Illumina | illumina | illumina.com
10x Genomics | 10xgenomics | 10xgenomics.com
Ginkgo Bioworks | ginkgobioworks | ginkgobioworks.com
Benchling | benchling | benchling.com
Verily | verily | verily.com
23andMe | 23andme | 23andme.com
Natera | natera | natera.com
BridgeBio Pharma | bridgebio | bridgebio.com
Moderna | moderna | moderna.com
BioNTech | biontech | biontech.com
Genentech | genentech | gene.com
Regeneron | regeneron | regeneron.com
Vertex Pharmaceuticals | vertex | vrtx.com
Eli Lilly | elililly | lilly.com
Johnson & Johnson | jnj | jnj.com
Pfizer | pfizer | pfizer.com
Merck | merck | merck.com
Roche | roche | roche.com
Novartis | novartis | novartis.com
Sanofi | sanofi | sanofi.com
GSK | gsk | gsk.com
Bayer | bayer | bayer.com
BASF | basf | basf.com
Dow | dow | dow.com
DuPont | dupont | dupont.com
Corning | corning | corning.com
3M | 3m | 3m.com
GE Aerospace | geaerospace | geaerospace.com
Honeywell | honeywell | honeywell.com
Eaton | eaton | eaton.com
Emerson | emerson | emerson.com
Rockwell Automation | rockwell | rockwellautomation.com
KUKA | kuka | kuka.com
ABB | abb | abb.com
Nokia | nokia | nokia.com
Ericsson | ericsson | ericsson.com
Juniper Networks | juniper | juniper.net
Arista Networks | arista | arista.com
Marvell | marvell | marvell.com
Micron | micron | micron.com
Qualcomm | qualcomm | qualcomm.com
AMD | amd | amd.com
Arm | arm | arm.com
ASML | asml | asml.com
Applied Materials | appliedmaterials | appliedmaterials.com
Lam Research | lamresearch | lamresearch.com
KLA | kla | kla.com
Synopsys | synopsys | synopsys.com
Cadence | cadence | cadence.com
Siemens Healthineers | siemenshealthineers | siemens-healthineers.com
Medtronic | medtronic | medtronic.com
Stryker | stryker | stryker.com
Boston Scientific | bostonscientific | bostonscientific.com
Philips Healthcare | philipshealthcare | philips.com
GE HealthCare | gehealthcare | gehealthcare.com
ResMed | resmed | resmed.com
Mammoth Biosciences | mammoth | mammoth.bio
Carbon Robotics | carbonrobotics | carbonrobotics.com
Impossible Foods | impossiblefoods | impossiblefoods.com
Beyond Meat | beyondmeat | beyondmeat.com
Oatly | oatly | oatly.com
Chobani | chobani | chobani.com
Sweetgreen | sweetgreen | sweetgreen.com
DoorDash | doordash | doordash.com
Uber | uber | uber.com
Lyft | lyft | lyft.com
Airbnb | airbnb | airbnb.com
Expedia Group | expediagroup | expediagroup.com
Booking Holdings | bookingholdings | bookingholdings.com
Tripadvisor | tripadvisor | tripadvisor.com
Marriott | marriott | marriott.com
Hilton | hilton | hilton.com
Hyatt | hyatt | hyatt.com
United Airlines | united | united.com
Delta Air Lines | delta | delta.com
Southwest Airlines | southwest | southwest.com
JetBlue | jetblue | jetblue.com
Alaska Airlines | alaskaair | alaskaair.com
American Airlines | americanair | aa.com
Emirates | emirates | emirates.com
Qantas | qantas | qantas.com
Deutsche Bahn | deutschebahn | deutschebahn.com
Uber Freight | uberfreight | uberfreight.com
Flexport | flexport | flexport.com
Convoy | convoy | convoy.com
Project44 | project44 | project44.com
ShipBob | shipbob | shipbob.com
Shippo | shippo | goshippo.com
Stord | stord | stord.com
FourKites | fourkites | fourkites.com
Kuehne+Nagel | kuehnenagel | kuehne-nagel.com
Maersk | maersk | maersk.com
DP World | dpworld | dpworld.com
Prologis | prologis | prologis.com
CBRE | cbre | cbre.com
JLL | jll | jll.com
WeWork | wework | wework.com
IWG | iwg | iwgplc.com
Regus | regus | regus.com
Hines | hines | hines.com
Keller Williams | kw | kw.com
RE/MAX | remax | remax.com
Coldwell Banker | coldwellbanker | coldwellbanker.com
Better.com | better | better.com
LendingTree | lendingtree | lendingtree.com
SoFi Technologies | sofi-technologies | sofi.com
NerdWallet | nerdwallet | nerdwallet.com
The Motley Fool | fool | fool.com
Morningstar | morningstar | morningstar.com
Bloomberg | bloomberg | bloomberg.com
Thomson Reuters | thomsonreuters | thomsonreuters.com
FactSet | factset | factset.com
S&P Global | spglobal | spglobal.com
BlackRock | blackrock | blackrock.com
Goldman Sachs | goldmansachs | goldmansachs.com
Morgan Stanley | morganstanley | morganstanley.com
JPMorgan Chase | jpmorganchase | jpmorganchase.com
Citigroup | citigroup | citigroup.com
Capital One | capitalone | capitalone.com
American Express | americanexpress | americanexpress.com
Discover Financial | discover | discover.com
Fidelity Investments | fidelity | fidelity.com
Charles Schwab | schwab | schwab.com
Vanguard | vanguard | vanguard.com
State Street | statestreet | statestreet.com
Northern Trust | northerntrust | northerntrust.com
Visa | visa | visa.com
Mastercard | mastercard | mastercard.com
American Express | americanexpress | americanexpress.com
Deloitte | deloitte | deloitte.com
Accenture | accenture | accenture.com
PwC | pwc | pwc.com
EY | ey | ey.com
KPMG | kpmg | kpmg.com
Bain & Company | bain | bain.com
Boston Consulting Group | bcg | bcg.com
McKinsey & Company | mckinsey | mckinsey.com
Oliver Wyman | oliverwyman | oliverwyman.com
Mercer | mercer | mercer.com
Willis Towers Watson | wtw | wtwco.com
Marsh McLennan | marshmclennan | marshmclennan.com
RSM | rsm | rsmus.com
Grant Thornton | grantthornton | grantthornton.com
Hewlett Packard Enterprise | hpe | hpe.com
Dell Technologies | delltechnologies | dell.com
Lenovo | lenovo | lenovo.com
Cisco | cisco | cisco.com
IBM | ibm | ibm.com
Oracle | oracle | oracle.com
SAP | sap | sap.com
ServiceNow | servicenow | servicenow.com
Workday | workday | workday.com
Intuit | intuit | intuit.com
ADP | adp | adp.com
Fiserv | fiserv | fiserv.com
FIS | fis | fisglobal.com
Paychex | paychex | paychex.com
Tata Consultancy Services | tcs | tcs.com
Infosys | infosys | infosys.com
Wipro | wipro | wipro.com
HCLTech | hcltech | hcltech.com
Capgemini | capgemini | capgemini.com
EPAM | epam | epam.com
Globant | globant | globant.com
Thoughtworks | thoughtworks | thoughtworks.com
Endava | endava | endava.com
Slalom | slalom | slalom.com
Publicis Groupe | publicis | publicisgroupe.com
WPP | wpp | wpp.com
Omnicom Group | omnicom | omnicomgroup.com
R/GA | rga | rga.com
IDEO | ideo | ideo.com
AKQA | akqa | akqa.com
VaynerMedia | vaynermedia | vaynermedia.com
GitLab | gitlab | gitlab.com
GitHub | github | github.com
Atlassian | atlassian | atlassian.com
JetBrains | jetbrains | jetbrains.com
Unity Technologies | unitytechnologies | unity.com
Canonical | canonical | canonical.com
Red Hat | redhat | redhat.com
SUSE | suse | suse.com
Docker | docker | docker.com
HashiCorp | hashicorp | hashicorp.com
Grafana Labs | grafana | grafana.com
Elastic | elastic | elastic.co
MongoDB | mongodb | mongodb.com
Redis | redis | redis.com
Neo4j | neo4j | neo4j.com
DataStax | datastax | datastax.com
Cloudera | cloudera | cloudera.com
Confluent | confluent | confluent.io
Snowplow | snowplow | snowplow.io
ClickHouse | clickhouse | clickhouse.com
Timescale | timescale | timescale.com
Cockroach Labs | cockroachlabs | cockroachlabs.com
Yugabyte | yugabyte | yugabyte.com
Vitess | vitess | vitess.io
Apache Software Foundation | apache | apache.org
Linux Foundation | linuxfoundation | linuxfoundation.org
Kubernetes | kubernetes | kubernetes.io
OpenAI | openai | openai.com
Anthropic | anthropic | anthropic.com
Google DeepMind | deepmind | deepmind.google
Meta AI | metaai | meta.com
Microsoft AI | microsoftai | microsoft.com
Amazon Web Services | aws | amazon.com
NVIDIA | nvidia | nvidia.com
Tesla | tesla | tesla.com
Apple | apple | apple.com
Netflix | netflix | netflix.com
TikTok | tiktok | tiktok.com
ByteDance | bytedance | bytedance.com
Snap Inc. | snapinc | snap.com
Pinterest | pinterest | pinterest.com
Reddit | reddit | reddit.com
Discord | discord | discord.com
Fandom | fandom | fandom.com
Stack Overflow | stackoverflow | stackoverflow.com
Stack Exchange | stackexchange | stackexchange.com
Indeed | indeed | indeed.com
LinkedIn | linkedin | linkedin.com
Glassdoor | glassdoor | glassdoor.com
ZipRecruiter | ziprecruiter | ziprecruiter.com
Upwork | upwork | upwork.com
Fiverr | fiverr | fiverr.com
Freelancer.com | freelancer | freelancer.com
Toptal | toptal | toptal.com
Hired | hired | hired.com
Robert Half | roberthalf | roberthalf.com
Kelly Services | kellyservices | kellyservices.com
Randstad | randstad | randstad.com
Adecco | adecco | adecco.com
ManpowerGroup | manpowergroup | manpowergroup.com
Robert Walters | robertwalters | robertwalters.com
PageGroup | pagegroup | page.com
Jobandtalent | jobandtalent | jobandtalent.com
Workable | workable | workable.com
Greenhouse Software | greenhouse | greenhouse.io
Lever | lever | lever.co
Ashby | ashby | ashbyhq.com
SmartRecruiters | smartrecruiters | smartrecruiters.com
Hospitable | hospitable | hospitable.com
Bunq | bunq | bunq.com
Vandebron | vandebron | vandebron.com
Channable | channable | channable.com
Happeo | happeo | happeo.com
Personio | personio | personio.com
GetJet Airlines | getjet | getjet.com
Omnicare | omnicare | omnicare.com
Hive | hive | hive.com
Decidr | decidr | decidr.ai
"""

# Extra board tokens to try for companies whose ATS slug is not the plain name.
ALIASES: dict[str, list[str]] = {
    "scaleai": ["scale"],
    "checkoutcom": ["checkout"],
    "huggingface": ["hugging-face"],
    "weightsandbiases": ["wandb"],
    "dbtlabs": ["dbt"],
    "1password": ["one-password"],
    "paloaltonetworks": ["palo-alto-networks"],
    "abnormalsecurity": ["abnormal"],
    "materialsecurity": ["material"],
    "onemedical": ["one-medical"],
    "warbyparker": ["warby-parker"],
    "cityblock": ["cityblockhealth"],
    "cloverhealth": ["clover"],
    "devotedhealth": ["devoted"],
    "carbonhealth": ["carbon"],
    "flatironhealth": ["flatiron"],
    "ginkgobioworks": ["ginkgo"],
    "virtahealth": ["virta"],
    "omadahealth": ["omada"],
    "lyrahealth": ["lyra"],
    "springhealth": ["spring"],
    "modernhealth": ["modern"],
    "sondermind": ["sonder"],
    "hims": ["himsandhers"],
    "billcom": ["bill"],
    "10xgenomics": ["10x-genomics"],
    "siemenshealthineers": ["siemens-healthineers"],
    "mercedesbenz": ["mercedes-benz"],
    "dominos": ["dominos-pizza"],
    "booking": ["bookingcom"],
    "cocacola": ["coca-cola"],
    "hm": ["handm"],
    "decidr": ["decidrai-1746526321"],
}

# Already in the registry; keep their existing, verified provider mapping.
KNOWN = {"notion", "openai", "snowflake", "spotify", "paytm", "bosch", "gitlab"}

STOPWORDS = {"the", "and", "of", "at", "jobs", "job", "careers", "career", "board"}


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def tokens(value: str) -> set[str]:
    parts = re.split(r"[^a-z0-9]+", value.lower())
    return {part for part in parts if len(part) >= 2 and part not in STOPWORDS}


def same_company(candidate: str, reported: str | None) -> bool:
    """Conservative identity check against the provider-reported name."""
    if not reported:
        return False
    left, right = normalize(candidate), normalize(reported)
    if not left or not right:
        return False
    if left == right:
        return True
    candidate_tokens, reported_tokens = tokens(candidate), tokens(reported)
    if candidate_tokens and candidate_tokens <= reported_tokens:
        return True
    if reported_tokens and reported_tokens <= candidate_tokens:
        return True
    # Short names such as H&M or EY have no usable tokens.
    if not candidate_tokens and len(left) >= 2 and left in right:
        return True
    return False


@dataclass
class Hit:
    candidate: str
    domain: str
    provider: str
    board: str
    reported_name: str | None
    jobs: int
    source_url: str
    identity_ok: bool


async def request_json(
    client: httpx.AsyncClient, url: str, params: dict[str, Any] | None = None
) -> Any | None:
    for attempt in range(3):
        try:
            response = await client.get(url, params=params)
        except httpx.HTTPError:
            if attempt == 2:
                return None
            await asyncio.sleep(1.5 * (attempt + 1))
            continue
        if response.status_code == 404:
            return None
        if response.status_code == 429 or response.status_code >= 500:
            if attempt == 2:
                return None
            retry_after = response.headers.get("retry-after")
            delay = float(retry_after) if retry_after and retry_after.isdigit() else 2.0 * (attempt + 1)
            await asyncio.sleep(min(delay, 20))
            continue
        if response.status_code != 200:
            return None
        try:
            return response.json()
        except ValueError:
            return None
    return None


async def request_text(
    client: httpx.AsyncClient, url: str, params: dict[str, Any] | None = None
) -> str | None:
    for attempt in range(3):
        try:
            response = await client.get(url, params=params)
        except httpx.HTTPError:
            if attempt == 2:
                return None
            await asyncio.sleep(1.5 * (attempt + 1))
            continue
        if response.status_code == 404:
            return None
        if response.status_code == 429 or response.status_code >= 500:
            if attempt == 2:
                return None
            retry_after = response.headers.get("retry-after")
            delay = (
                float(retry_after)
                if retry_after and retry_after.replace(".", "", 1).isdigit()
                else 2.0 * (attempt + 1)
            )
            await asyncio.sleep(min(delay, 20))
            continue
        if response.status_code != 200:
            return None
        return response.text
    return None


def _xml_count_and_title(
    payload: str, item_path: str, title_path: str
) -> tuple[int, str | None]:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        return 0, None
    items = root.findall(item_path)
    title = root.findtext(title_path)
    return len(items), title.strip() if isinstance(title, str) and title.strip() else None


def _xml_first_text(root: ET.Element, path: str) -> str | None:
    for element in root.findall(path):
        if isinstance(element.text, str) and element.text.strip():
            return element.text.strip()
    return None


async def page_title(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        response = await client.get(url)
    except httpx.HTTPError:
        return None
    if response.status_code != 200:
        return None
    match = re.search(r"<title[^>]*>(.*?)</title>", response.text or "", re.I | re.S)
    if not match:
        return None
    return re.sub(r"\s+", " ", match.group(1)).strip() or None


async def probe_greenhouse(
    client: httpx.AsyncClient, candidate: str, domain: str, token: str
) -> Hit | None:
    meta = await request_json(
        client, f"https://boards-api.greenhouse.io/v1/boards/{token}"
    )
    if not isinstance(meta, dict) or not meta.get("name"):
        return None
    payload = await request_json(
        client,
        f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs",
        {"content": "false"},
    )
    jobs = payload.get("jobs") if isinstance(payload, dict) else None
    count = len(jobs) if isinstance(jobs, list) else 0
    return Hit(
        candidate=candidate,
        domain=domain,
        provider="greenhouse",
        board=token,
        reported_name=str(meta["name"]),
        jobs=count,
        source_url=f"https://boards.greenhouse.io/{token}",
        identity_ok=same_company(candidate, str(meta["name"])),
    )


async def probe_lever(
    client: httpx.AsyncClient, candidate: str, domain: str, token: str
) -> Hit | None:
    payload = await request_json(
        client, f"https://api.lever.co/v0/postings/{token}", {"mode": "json"}
    )
    if not isinstance(payload, list) or not payload:
        return None
    title = await page_title(client, f"https://jobs.lever.co/{token}")
    return Hit(
        candidate=candidate,
        domain=domain,
        provider="lever",
        board=token,
        reported_name=title,
        jobs=len(payload),
        source_url=f"https://jobs.lever.co/{token}",
        identity_ok=same_company(candidate, title),
    )


async def probe_ashby(
    client: httpx.AsyncClient, candidate: str, domain: str, token: str
) -> Hit | None:
    title = await page_title(client, f"https://jobs.ashbyhq.com/{token}")
    if not title:
        return None
    if not same_company(candidate, title):
        return Hit(
            candidate=candidate,
            domain=domain,
            provider="ashby",
            board=token,
            reported_name=title,
            jobs=0,
            source_url=f"https://jobs.ashbyhq.com/{token}",
            identity_ok=False,
        )
    payload = await request_json(
        client,
        f"https://api.ashbyhq.com/posting-api/job-board/{token}",
        {"includeCompensation": "false"},
    )
    jobs = payload.get("jobs") if isinstance(payload, dict) else None
    return Hit(
        candidate=candidate,
        domain=domain,
        provider="ashby",
        board=token,
        reported_name=title,
        jobs=len(jobs) if isinstance(jobs, list) else 0,
        source_url=f"https://jobs.ashbyhq.com/{token}",
        identity_ok=True,
    )


async def probe_smartrecruiters(
    client: httpx.AsyncClient, candidate: str, domain: str, token: str
) -> Hit | None:
    payload = await request_json(
        client,
        f"https://api.smartrecruiters.com/v1/companies/{token}/postings",
        {"limit": 1},
    )
    if not isinstance(payload, dict):
        return None
    total = payload.get("totalFound")
    if not isinstance(total, int) or total <= 0:
        return None
    content = payload.get("content") or []
    company = (content[0].get("company") if content else None) or {}
    reported = company.get("name") or company.get("identifier") or token
    identifier = company.get("identifier") or token
    return Hit(
        candidate=candidate,
        domain=domain,
        provider="smartrecruiters",
        board=str(identifier),
        reported_name=str(reported),
        jobs=total,
        source_url=f"https://careers.smartrecruiters.com/{identifier}",
        identity_ok=same_company(candidate, str(reported)),
    )


async def probe_recruitee(
    client: httpx.AsyncClient, candidate: str, domain: str, token: str
) -> Hit | None:
    url = f"https://{token}.recruitee.com/api/offers"
    payload = await request_json(client, url)
    if not isinstance(payload, dict) or not isinstance(payload.get("offers"), list):
        return None
    offers = [offer for offer in payload["offers"] if isinstance(offer, dict)]
    if not offers:
        return None
    reported = next(
        (
            str(offer["company_name"])
            for offer in offers
            if offer.get("company_name")
        ),
        None,
    )
    return Hit(
        candidate=candidate,
        domain=domain,
        provider="recruitee",
        board=token,
        reported_name=reported,
        jobs=len(offers),
        source_url=f"https://{token}.recruitee.com/",
        identity_ok=same_company(candidate, reported),
    )


async def probe_workable(
    client: httpx.AsyncClient, candidate: str, domain: str, token: str
) -> Hit | None:
    url = f"https://apply.workable.com/api/v1/widget/accounts/{token}"
    payload = await request_json(client, url, {"details": "true"})
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        return None
    jobs = [job for job in payload["jobs"] if isinstance(job, dict)]
    if not jobs:
        return None
    reported = payload.get("name")
    return Hit(
        candidate=candidate,
        domain=domain,
        provider="workable",
        board=token,
        reported_name=str(reported) if reported else None,
        jobs=len(jobs),
        source_url=f"https://apply.workable.com/{token}/",
        identity_ok=same_company(candidate, str(reported) if reported else None),
    )


async def probe_personio(
    client: httpx.AsyncClient, candidate: str, domain: str, token: str
) -> Hit | None:
    url = f"https://{token}.jobs.personio.de/xml"
    payload = await request_text(client, url, {"language": "en"})
    if not payload:
        return None
    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        return None
    positions = root.findall("./position")
    if not positions:
        return None
    reported = _xml_first_text(root, "./position/subcompany")
    return Hit(
        candidate=candidate,
        domain=domain,
        provider="personio",
        board=token,
        reported_name=reported,
        jobs=len(positions),
        source_url=f"https://{token}.jobs.personio.de/",
        identity_ok=same_company(candidate, reported),
    )


async def probe_teamtailor(
    client: httpx.AsyncClient, candidate: str, domain: str, token: str
) -> Hit | None:
    url = f"https://{token}.teamtailor.com/jobs.rss"
    payload = await request_text(client, url, {"per_page": 200})
    if not payload:
        return None
    count, reported = _xml_count_and_title(
        payload, "./channel/item", "./channel/title"
    )
    if count <= 0:
        return None
    return Hit(
        candidate=candidate,
        domain=domain,
        provider="teamtailor",
        board=token,
        reported_name=reported,
        jobs=count,
        source_url=f"https://{token}.teamtailor.com/jobs",
        identity_ok=same_company(candidate, reported),
    )


PROBES = {
    "greenhouse": probe_greenhouse,
    "lever": probe_lever,
    "ashby": probe_ashby,
    "smartrecruiters": probe_smartrecruiters,
    "recruitee": probe_recruitee,
    "workable": probe_workable,
    "personio": probe_personio,
    "teamtailor": probe_teamtailor,
}


async def run(output: str) -> int:
    candidates = []
    for line in (
        CANDIDATES_RAW.strip() + "\n" + EXTRA_CANDIDATES_RAW.strip()
    ).splitlines():
        name, slug, domain = (part.strip() for part in line.split("|"))
        if slug in KNOWN:
            continue
        candidates.append((name, slug, domain))

    semaphore = asyncio.Semaphore(CONCURRENCY)
    hits: list[Hit] = []
    started = time.perf_counter()

    async def guarded(
        provider: str, name: str, domain: str, token: str
    ) -> Hit | None:
        async with semaphore:
            try:
                return await PROBES[provider](client, name, domain, token)
            except Exception as exc:  # noqa: BLE001 - discovery reports, never crashes
                print(f"! {provider} {token}: {exc}", file=sys.stderr)
                return None
            finally:
                await asyncio.sleep(0.05)

    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    async with httpx.AsyncClient(
        timeout=TIMEOUT,
        headers=headers,
        follow_redirects=True,
        limits=httpx.Limits(max_connections=16, max_keepalive_connections=8),
    ) as client:
        tasks = []
        for name, slug, domain in candidates:
            tokens_to_try = [slug, *ALIASES.get(slug, [])]
            for token in dict.fromkeys(tokens_to_try):
                for provider in PROBES:
                    tasks.append(guarded(provider, name, domain, token))
        for completed, result in enumerate(
            await asyncio.gather(*tasks), start=1
        ):
            if result is not None:
                hits.append(result)
            if completed % 100 == 0:
                print(f"... {completed}/{len(tasks)} probes", file=sys.stderr)

    # Pick one verified board per candidate: the one with the most live jobs.
    best: dict[str, Hit] = {}
    for hit in hits:
        if not hit.identity_ok or hit.jobs <= 0:
            continue
        current = best.get(hit.candidate)
        if current is None or hit.jobs > current.jobs:
            best[hit.candidate] = hit

    verified = sorted(best.values(), key=lambda item: (-item.jobs, item.candidate))
    rejected = sorted(
        (hit for hit in hits if not hit.identity_ok),
        key=lambda item: (item.candidate, item.provider),
    )
    unmatched = sorted(
        (
            hit
            for hit in hits
            if hit.identity_ok and hit.jobs <= 0 and hit.provider == "ashby"
        ),
        key=lambda item: item.candidate,
    )

    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "elapsed_seconds": round(time.perf_counter() - started, 1),
        "candidates": len(candidates),
        "probes": len(tasks),
        "verified": [asdict(hit) for hit in verified],
        "rejected_identity": [asdict(hit) for hit in rejected],
        "empty": [asdict(hit) for hit in unmatched],
        "all_hits": [asdict(hit) for hit in sorted(hits, key=lambda h: (h.candidate, h.provider))],
    }
    with open(output, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)

    print(
        f"verified {len(verified)} boards across "
        f"{len({hit.provider for hit in verified})} providers "
        f"({sum(hit.jobs for hit in verified):,} jobs) in "
        f"{payload['elapsed_seconds']}s -> {output}"
    )
    for hit in verified:
        print(
            f"  {hit.provider:16} {hit.board:28} {hit.jobs:>6}  "
            f"{hit.candidate} ({hit.reported_name})"
        )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default="scripts/board_discovery.json",
        help="Where to write the discovery report",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.output)))


if __name__ == "__main__":
    main()
