"""Regenerate the marked sections of README.md from the GitHub API.

Two blocks are filled in:
  recent_releases  -- newest releases across my own repos and my orgs
  recent_projects  -- repos I pushed to most recently

Run locally with GH_TOKEN set, or let .github/workflows/build.yml do it.
"""

import itertools
import os
import pathlib
import re

from github import Auth, Github

# --- config -----------------------------------------------------------------

USER = "gloiiire"
ORGS = ["ONTBible", "pinkha-app"]

# Forks are skipped: their releases and commits are not mine. Add a full name
# here to keep one anyway (e.g. a fork I actively develop).
FORKS_TO_KEEP = set()

RELEASES_SHOWN = 6
PROJECTS_SHOWN = 6
TITLE_MAX_LEN = 42

# --- helpers ----------------------------------------------------------------

EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "☀-➿"
    "️‍"
    "]+",
    flags=re.UNICODE,
)


def clean(text):
    """Strip emoji and collapse whitespace so the two columns stay aligned."""
    text = EMOJI_RE.sub("", text or "")
    return re.sub(r"\s+", " ", text).strip()


def truncate_middle(text, max_len=TITLE_MAX_LEN):
    """Shorten from the middle: long titles keep both their start and their end."""
    text = clean(text)
    if len(text) <= max_len:
        return text
    keep = max_len - 3
    left = (keep + 1) // 2
    return f"{text[:left]}...{text[-(keep // 2):]}"


def replace_chunk(content, marker, chunk):
    pattern = re.compile(
        r"<!-- {} starts -->.*<!-- {} ends -->".format(marker, marker), re.DOTALL
    )
    return pattern.sub(
        "<!-- {} starts -->\n{}\n<!-- {} ends -->".format(marker, chunk, marker),
        content,
    )


def as_bullets(lines):
    """Join with <br> — inside an HTML <td>, real newlines would collapse."""
    return "<br>".join(lines) if lines else "_Nothing yet._"


# --- collection -------------------------------------------------------------


def collect_repos(gh):
    repos = list(gh.get_user(USER).get_repos())
    for org in ORGS:
        repos.extend(gh.get_organization(org).get_repos())

    keep = []
    seen = set()
    for repo in repos:
        if repo.private or repo.archived or repo.full_name in seen:
            continue
        if repo.fork and repo.full_name not in FORKS_TO_KEEP:
            continue
        seen.add(repo.full_name)
        keep.append(repo)
    return keep


def recent_releases(repos):
    found = []
    for repo in repos:
        for release in itertools.islice(repo.get_releases(), 3):
            if release.draft or release.prerelease:
                continue
            title = truncate_middle(f"{repo.name} {release.tag_name}")
            found.append((release.published_at, title, release.html_url))

    found.sort(reverse=True)
    return as_bullets(
        [
            f"• [{title}]({url}) - {date:%Y-%m-%d}"
            for date, title, url in found[:RELEASES_SHOWN]
        ]
    )


def recent_projects(repos):
    ranked = sorted(repos, key=lambda r: r.pushed_at, reverse=True)
    return as_bullets(
        [
            f"• [{truncate_middle(repo.name)}]({repo.html_url}) - {repo.pushed_at:%Y-%m-%d}"
            for repo in ranked[:PROJECTS_SHOWN]
        ]
    )


# --- main -------------------------------------------------------------------

if __name__ == "__main__":
    gh = Github(auth=Auth.Token(os.environ["GH_TOKEN"]))
    repos = collect_repos(gh)

    readme = pathlib.Path(__file__).parent / "README.md"
    content = readme.read_text()
    content = replace_chunk(content, "recent_releases", recent_releases(repos))
    content = replace_chunk(content, "recent_projects", recent_projects(repos))
    readme.write_text(content)
