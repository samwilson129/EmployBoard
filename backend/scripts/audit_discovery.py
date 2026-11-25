import asyncio
import json
import re

import httpx

with open("scripts/board_discovery.json", encoding="utf-8") as handle:
    data = json.load(handle)

verified = data["verified"]
print(f"verified={len(verified)} jobs={sum(v['jobs'] for v in verified):,}")
print("\nBy provider:")
for provider in (
    "greenhouse",
    "lever",
    "ashby",
    "smartrecruiters",
    "recruitee",
    "workable",
    "personio",
    "teamtailor",
):
    rows = [v for v in verified if v["provider"] == provider]
    print(f"  {provider:16} boards={len(rows):3} jobs={sum(r['jobs'] for r in rows):6,}")

print("\nCandidates with multiple hits:")
by_candidate: dict[str, list] = {}
for hit in data["all_hits"]:
    by_candidate.setdefault(hit["candidate"], []).append(hit)
for candidate, hits in sorted(by_candidate.items()):
    if len(hits) > 1:
        summary = ", ".join(
            f"{h['provider']}:{h['board']}={h['jobs']}{'' if h['identity_ok'] else '(reject)'}"
            for h in hits
        )
        print(f"  {candidate}: {summary}")

print("\nRejected identity hits:")
for hit in data["rejected_identity"]:
    print(
        f"  {hit['candidate']:22} {hit['provider']:16} {hit['board']:24} "
        f"jobs={hit['jobs']:<6} reported={hit['reported_name']!r}"
    )

print("\nSmartRecruiters boards:")
for hit in verified:
    if hit["provider"] == "smartrecruiters":
        print(f"  {hit['board']:24} {hit['jobs']:>6} {hit['reported_name']!r}")

SUSPECT = ["Together", "GONG", "Glean", "Uber", "Wayfair", "Neon", "Remote", "Calm"]


async def main() -> None:
    headers = {"User-Agent": "EmployBoard/1.0 (audit)", "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=30, headers=headers, follow_redirects=True) as client:
        for hit in verified:
            if hit["candidate"] not in SUSPECT:
                continue
            print(f"\n--- {hit['candidate']} ({hit['provider']} {hit['board']}) ---")
            if hit["provider"] == "smartrecruiters":
                response = await client.get(
                    f"https://api.smartrecruiters.com/v1/companies/{hit['board']}/postings",
                    params={"limit": 5},
                )
                if response.status_code == 200:
                    for job in response.json().get("content", []):
                        company = (job.get("company") or {}).get("name")
                        print(f"   {job.get('name')!r} company={company!r}")
            elif hit["provider"] == "greenhouse":
                response = await client.get(
                    f"https://boards-api.greenhouse.io/v1/boards/{hit['board']}/jobs"
                )
                if response.status_code == 200:
                    for job in response.json().get("jobs", [])[:5]:
                        print(f"   {job.get('title')!r} {job.get('absolute_url')}")
            elif hit["provider"] == "lever":
                response = await client.get(
                    f"https://api.lever.co/v0/postings/{hit['board']}", params={"mode": "json", "limit": 5}
                )
                if response.status_code == 200:
                    for job in response.json()[:5]:
                        print(f"   {job.get('text')!r} {job.get('hostedUrl')}")


asyncio.run(main())
