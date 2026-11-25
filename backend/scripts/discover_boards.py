"""Discover real public ATS boards for a curated list of companies.

This maintenance tool only uses the documented public posting APIs:

* Greenhouse  https://boards-api.greenhouse.io/v1/boards/{board}/jobs
* Lever       https://api.lever.co/v0/postings/{board}?mode=json
* Ashby       https://api.ashbyhq.com/posting-api/job-board/{board}
* SmartRecruiters https://api.smartrecruiters.com/v1/companies/{id}/postings

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


PROBES = {
    "greenhouse": probe_greenhouse,
    "lever": probe_lever,
    "ashby": probe_ashby,
    "smartrecruiters": probe_smartrecruiters,
}


async def run(output: str) -> int:
    candidates = []
    for line in CANDIDATES_RAW.strip().splitlines():
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
