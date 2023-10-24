#!/usr/bin/python3

from typing import Dict, Optional, Set, Tuple, Any, cast
from aiohttp import ClientSession
from datetime import date, timedelta

from src.env_vars import EnvironmentVariables
from src.github_api_queries import GitHubApiQueries

###############################################################################
# GitHubRepoStats class
###############################################################################


class GitHubRepoStats(object):
    """
    Retrieve and store statistics about GitHub usage.
    """

    _DATE_FORMAT = "%Y-%m-%d"
    _EXCLUDED_USER_NAMES = [
        "dependabot[bot]"
    ]  # exclude bot data from being included in statistical calculations
    _NO_NAME = "No Name"

    def __init__(self, environment_vars: EnvironmentVariables, session: ClientSession):
        self.environment_vars: EnvironmentVariables = environment_vars
        self.queries = GitHubApiQueries(
            username=self.environment_vars.username,
            access_token=self.environment_vars.access_token,
            session=session,
        )

        self._name: Optional[str] = None
        self._stargazers: Optional[int] = None
        self._forks: Optional[int] = None
        self._total_contributions: Optional[int] = None
        self._languages: Optional[Dict[str, Any]] = None
        self._excluded_languages: Optional[Set[str]] = None
        self._repos: Optional[Set[str]] = None
        self._owned_repos: Optional[Set[str]] = None
        self._users_lines_changed: Optional[Tuple[int, int]] = None
        self._avg_percent: Optional[str] = None
        self._weighted_avg_percent: Optional[str] = None
        self._views: Optional[int] = None
        self._collaborators: Optional[int] = None
        self._collaborator_set: Optional[Set[str]] = None
        self._contributors: Optional[Set[str]] = None
        self._views_from_date: Optional[str] = None
        self._pull_requests: Optional[int] = None
        self._issues: Optional[int] = None
        self._empty_repos: Optional[Set[str]] = None
        self._collab_repos: Optional[Set[str]] = None
        self._is_fetch_rate_limit_exceeded: Optional[bool] = False

    async def to_str(self) -> str:
        """
        :return: summary of all available statistics
        """
        languages = await self.languages_proportional
        formatted_languages = "\n\t\t\t- ".join(
            [f"{k}: {v:0.4f}%" for k, v in languages.items()]
        )

        users_lines_changed = await self.lines_changed
        avg_percent = await self.avg_contribution_percent
        weighted_avg_percent = await self.weighted_avg_contribution_percent
        contributors = max(len(await self.contributors) - 1, 0)

        return f"""GitHub Repository Statistics:
        Stargazers: {await self.stargazers:,}
        Forks: {await self.forks:,}
        Pull requests: {await self.pull_requests:,}
        Issues: {await self.issues:,}
        All-time contributions: {await self.total_contributions:,}
        Repositories with contributions: {len(await self.repos):,}
        Lines of code added: {users_lines_changed[0]:,}
        Lines of code deleted: {users_lines_changed[1]:,}
        Total lines of code changed: {sum(users_lines_changed):,}
        Avg. % of contributions (per collab repo): {avg_percent}
        Weighted avg. % of contributions (per collab repo): {weighted_avg_percent}
        Project page views: {await self.views:,}
        Project page views from date: {await self.views_from_date}
        Project repository collaborators: {await self.collaborators:,}
        Project repository contributors: {contributors:,}
        Total number of languages: {len(list(languages.keys()))} (+{len(await self.excluded_languages):,})
        Languages:\n\t\t\t- {formatted_languages}"""

    async def is_repo_name_invalid(self, repo_name) -> bool:
        """
        Determines a repo name invalid if:
            - repo is already scraped and the name is in the list
            - repo name is not included in and only_include_repos is being used
            - repo name is included in exclude_repos
        :param repo_name: the name of the repo in owner/name format
        :return: True if repo is not to be included in self._repos
        """
        return (
            repo_name in self._repos
            or len(self.environment_vars.only_included_repos) > 0
            and repo_name not in self.environment_vars.only_included_repos
            or repo_name in self.environment_vars.exclude_repos
        )

    async def is_repo_type_excluded(self, repo_data) -> bool:
        """
        Determines a repo type excluded if:
            - repo is a fork and forked repos are not being included
            - repo is archived and archived repos are being excluded
            - repo is private and private repos are being excluded
            - repo is public and public repos are being excluded
        :param repo_data: repo data returned from API fetch
        :return: True if repo type is not to be included in self._repos
        """
        return (
            not self.environment_vars.include_forked_repos
            and (repo_data.get("isFork") or repo_data.get("fork"))
            or self.environment_vars.exclude_archive_repos
            and (repo_data.get("isArchived") or repo_data.get("archived"))
            or self.environment_vars.exclude_private_repos
            and (repo_data.get("isPrivate") or repo_data.get("private"))
            or self.environment_vars.exclude_public_repos
            and (not repo_data.get("isPrivate") or not repo_data.get("private"))
        )

    async def get_stats(self) -> None:
        """
        Get lots of summary stats using one big query. Sets many attributes
        """
        self._stargazers = 0
        self._forks = 0
        self._excluded_languages = set()
        self._languages = dict()
        self._repos = set()
        self._empty_repos = set()

        next_owned = None
        next_contrib = None

        while True:
            raw_results = await self.queries.query(
                GitHubApiQueries.repos_overview(
                    owned_cursor=next_owned, contrib_cursor=next_contrib
                )
            )
            raw_results = raw_results if raw_results is not None else {}

            self._name = raw_results.get("data", {}).get("viewer", {}).get("name", None)

            if self._name is None:
                self._name = (
                    raw_results.get("data", {})
                    .get("viewer", {})
                    .get("login", self._NO_NAME)
                )

            owned_repos = (
                raw_results.get("data", {}).get("viewer", {}).get("repositories", {})
            )
            repos = owned_repos.get("nodes", [])

            contrib_repos = (
                raw_results.get("data", {})
                .get("viewer", {})
                .get("repositoriesContributedTo", {})
            )

            if not self.environment_vars.exclude_contrib_repos:
                repos += contrib_repos.get("nodes", [])

            await self.repo_stats(repos)

            is_cur_owned = owned_repos.get("pageInfo", {}).get("hasNextPage", False)
            is_cur_contrib = contrib_repos.get("pageInfo", {}).get("hasNextPage", False)

            if is_cur_owned or is_cur_contrib:
                next_owned = owned_repos.get("pageInfo", {}).get(
                    "endCursor", next_owned
                )
                next_contrib = contrib_repos.get("pageInfo", {}).get(
                    "endCursor", next_contrib
                )
            else:
                break

        await self.manually_added_repo_stats()

        # TODO: Improve languages to scale by number of contributions to specific filetypes
        langs_total = sum([v.get("size", 0) for v in self._languages.values()])
        for k, v in self._languages.items():
            v["prop"] = 100 * (v.get("size", 0) / langs_total)

    async def repo_stats(self, repos) -> None:
        """
        Gathers statistical data from fetches for repos user is associated with on GitHub
        """
        for repo in repos:
            if not repo or await self.is_repo_type_excluded(repo):
                continue

            name = repo.get("nameWithOwner")
            if await self.is_repo_name_invalid(name):
                continue
            self._repos.add(name)

            self._stargazers += repo.get("stargazers").get("totalCount", 0)
            self._forks += repo.get("forkCount", 0)

            if repo.get("isEmpty"):
                self._empty_repos.add(name)
                continue

            for lang in repo.get("languages", {}).get("edges", []):
                name = lang.get("node", {}).get("name", "Other")
                languages = await self.languages

                if name in self.environment_vars.exclude_langs:
                    self._excluded_languages.add(name)
                    continue

                if name in languages:
                    languages[name]["size"] += lang.get("size", 0)
                    languages[name]["occurrences"] += 1
                else:
                    languages[name] = {
                        "size": lang.get("size", 0),
                        "occurrences": 1,
                        "color": lang.get("node", {}).get("color"),
                    }

    async def manually_added_repo_stats(self) -> None:
        """
        Gathers statistical data from fetches for manually added repos otherwise not fetched by user association
        """
        lang_cols = self.queries.get_language_colors()

        for repo in self.environment_vars.manually_added_repos:
            if await self.is_repo_name_invalid(repo):
                continue
            self._repos.add(repo)

            repo_stats = await self.queries.query_rest(f"/repos/{repo}")
            if await self.is_repo_type_excluded(repo_stats):
                continue

            self._stargazers += repo_stats.get("stargazers_count", 0)
            self._forks += repo_stats.get("forks", 0)

            if repo_stats.get("size") == 0:
                self._empty_repos.add(repo)
                continue

            if repo_stats.get("language"):
                langs = await self.queries.query_rest(f"/repos/{repo}/languages")

                for lang, size in langs.items():
                    languages = await self.languages

                    if lang in self.environment_vars.exclude_langs:
                        continue

                    if lang in languages:
                        languages[lang]["size"] += size
                        languages[lang]["occurrences"] += 1
                    else:
                        languages[lang] = {
                            "size": size,
                            "occurrences": 1,
                            "color": lang_cols.get(lang).get("color"),
                        }

    @property
    async def name(self) -> str:
        """
        :return: GitHub user's name
        """
        if self._name is not None:
            return self._name
        await self.get_stats()
        assert self._name is not None
        return self._name

    @property
    async def stargazers(self) -> int:
        """
        :return: total number of stargazers on user's repos
        """
        if self._stargazers is not None:
            return self._stargazers
        await self.get_stats()
        assert self._stargazers is not None
        return self._stargazers

    @property
    async def forks(self) -> int:
        """
        :return: total number of forks on user's repos
        """
        if self._forks is not None:
            return self._forks
        await self.get_stats()
        assert self._forks is not None
        return self._forks

    @property
    async def languages(self) -> Dict:
        """
        :return: summary of languages used by the user
        """
        if self._languages is not None:
            return self._languages
        await self.get_stats()
        assert self._languages is not None
        return self._languages

    @property
    async def excluded_languages(self) -> Set:
        """
        :return: summary of languages used by the user
        """
        if self._excluded_languages is not None:
            return self._excluded_languages
        await self.get_stats()
        assert self._excluded_languages is not None
        return self._excluded_languages

    @property
    async def languages_proportional(self) -> Dict:
        """
        :return: summary of languages used by the user, with proportional usage
        """
        if self._languages is None:
            await self.get_stats()
            assert self._languages is not None
        return {k: v.get("prop", 0) for (k, v) in self._languages.items()}

    @property
    async def repos(self) -> Set[str]:
        """
        :return: list of names of repos user is involved with
        """
        if self._repos is not None:
            return self._repos
        await self.get_stats()
        assert self._repos is not None
        return self._repos

    @property
    async def owned_repos(self) -> Set[str]:
        """
        :return: list of names of repos owned by user
        """
        if self._owned_repos is not None:
            return self._owned_repos
        await self.get_stats()
        assert self._repos is not None
        self._owned_repos = set(
            [
                i
                for i in self._repos
                if self.environment_vars.username == i.split("/")[0]
            ]
        )
        return self._owned_repos

    @property
    async def total_contributions(self) -> int:
        """
        :return: count of user's total contributions as defined by GitHub
        """
        if self._total_contributions is not None:
            return self._total_contributions
        self._total_contributions = 0

        years = (
            (await self.queries.query(GitHubApiQueries.contributions_all_years()))
            .get("data", {})
            .get("viewer", {})
            .get("contributionsCollection", {})
            .get("contributionYears", [])
        )

        by_year = (
            (await self.queries.query(GitHubApiQueries.all_contributions(years)))
            .get("data", {})
            .get("viewer", {})
            .values()
        )

        for year in by_year:
            self._total_contributions += year.get("contributionCalendar", {}).get(
                "totalContributions", 0
            )
        return cast(int, self._total_contributions)

    @property
    async def lines_changed(self) -> Tuple[int, int]:
        """
        Fetches total lines added and deleted for user and repository total
        Calculates total and average line changes for user
        Calculates total contributors
        :return: count of total lines added, removed, or modified by the user
        """
        if self._users_lines_changed is not None:
            return self._users_lines_changed
        _, collab_repos = await self.raw_collaborators()
        slave_status_repos = self.environment_vars.more_collab_repos

        contributor_set = set()
        repo_total_changes_arr = []
        author_contribution_percentages = []
        weighted_author_contribution_percentages = []
        author_total_additions = 0
        author_total_deletions = 0

        for repo in await self.repos:
            if repo in self._empty_repos:
                continue
            num_repo_collabs = 1
            other_authors_total_changes = 0
            author_additions = 0
            author_deletions = 0

            r = await self.queries.query_rest(f"/repos/{repo}/stats/contributors")

            for author_obj in r:
                # Handle malformed response from API by skipping this repo
                if not isinstance(author_obj, dict) or not isinstance(
                    author_obj.get("author", {}), dict
                ):
                    continue
                author = author_obj.get("author", {}).get("login", "")
                contributor_set.add(author)  # count number of total other contributors

                if (
                    author != self.environment_vars.username
                    and author not in self._EXCLUDED_USER_NAMES
                ):
                    for week in author_obj.get("weeks", []):
                        other_authors_total_changes += week.get("a", 0)
                        other_authors_total_changes += week.get("d", 0)
                        num_repo_collabs += 1
                else:
                    for week in author_obj.get("weeks", []):
                        author_additions += week.get("a", 0)
                        author_deletions += week.get("d", 0)
            author_total_additions += author_additions
            author_total_deletions += author_deletions

            # calculate average author's contributions to each repository with at least one other collaborator
            if (
                repo not in self.environment_vars.exclude_collab_repos
                and (author_additions + author_deletions) > 0
                and (
                    other_authors_total_changes > 0
                    or repo
                    in collab_repos
                    | slave_status_repos  # either collaborators are ghosting or no show in repo
                )
            ):
                repo_total_changes = (
                    other_authors_total_changes + author_additions + author_deletions
                )
                author_contribution_percentages.append(
                    (author_additions + author_deletions) / repo_total_changes
                )
                repo_total_changes_arr.append(repo_total_changes)

                weighted_author_contribution_percentages.append(
                    author_contribution_percentages[-1]
                    * (1 - 1 / num_repo_collabs if num_repo_collabs > 1 else 1)
                )

        if sum(author_contribution_percentages) > 0:
            self._avg_percent = f"{(sum(author_contribution_percentages) / len(repo_total_changes_arr) * 100):0.2f}%"

            weighted_avg_percent = sum(weighted_author_contribution_percentages) / len(
                repo_total_changes_arr
            )
            self._weighted_avg_percent = f"{weighted_avg_percent * 100:0.2f}%"
        else:
            self._weighted_avg_percent = self._avg_percent = "N/A"

        self._contributors = contributor_set

        self._users_lines_changed = (author_total_additions, author_total_deletions)
        return self._users_lines_changed

    @property
    async def avg_contribution_percent(self) -> str:
        """
        :return: str representing the avg percent of user's repo contributions
        """
        if self._avg_percent is not None:
            return self._avg_percent
        await self.lines_changed
        assert self._avg_percent is not None
        return self._avg_percent

    @property
    async def weighted_avg_contribution_percent(self) -> str:
        """
        :return: str representing the weighted avg percent of user's repo contributions
        """
        if self._weighted_avg_percent is not None:
            return self._weighted_avg_percent
        await self.lines_changed
        assert self._weighted_avg_percent is not None
        return self._weighted_avg_percent

    @property
    async def views(self) -> int:
        """
        Note: API returns a user's repository view data for the last 14 days.
        This counts views as of the initial date this code is first run in repo
        :return: view count of user's repositories as of a given (first) date
        """
        if self._views is not None:
            return self._views

        last_viewed = self.environment_vars.repo_last_viewed
        today = date.today().strftime(self._DATE_FORMAT)
        yesterday = (date.today() - timedelta(1)).strftime(self._DATE_FORMAT)
        dates = {last_viewed, yesterday}

        today_view_count = 0
        for repo in await self.repos:
            r = await self.queries.query_rest(f"/repos/{repo}/traffic/views")

            for view in r.get("views", []):
                if view.get("timestamp")[:10] == today:
                    today_view_count += view.get("count", 0)
                elif view.get("timestamp")[:10] > last_viewed:
                    self.environment_vars.set_views(view.get("count", 0))
                    dates.add(view.get("timestamp")[:10])

        if last_viewed == "0000-00-00":
            dates.remove(last_viewed)

        if self.environment_vars.store_repo_view_count:
            self.environment_vars.set_last_viewed(yesterday)

            if self.environment_vars.repo_first_viewed == "0000-00-00":
                self.environment_vars.repo_first_viewed = min(dates)
            self.environment_vars.set_first_viewed(
                self.environment_vars.repo_first_viewed
            )
            self._views_from_date = self.environment_vars.repo_first_viewed
        else:
            self._views_from_date = min(dates)

        self._views = self.environment_vars.repo_views + today_view_count
        return self._views

    @property
    async def views_from_date(self) -> str:
        """
        :return: the first date included in the repo view count
        """
        if self._views_from_date is not None:
            return self._views_from_date
        await self.views
        assert self._views_from_date is not None
        return self._views_from_date

    async def raw_collaborators(self) -> (Set, Set):
        if self._collaborator_set is not None and self._collab_repos is not None:
            return self._collaborator_set, self._collab_repos

        self._collaborator_set = set()
        self._collab_repos = set()

        for repo in await self.repos:
            r = await self.queries.query_rest(f"/repos/{repo}/collaborators")
            collab_count = 0

            for obj in r:
                if isinstance(obj, dict):
                    collab_count += 1
                    self._collaborator_set.add(obj.get("login"))

                    if collab_count > 1:
                        self._collab_repos.add(repo)

        return self._collaborator_set, self._collab_repos

    @property
    async def collaborators(self) -> int:
        """
        :return: count of total collaborators to user's repositories
        """
        if self._collaborators is not None:
            return self._collaborators

        collaborator_set, _ = await self.raw_collaborators()
        collaborators = max(0, len(collaborator_set.union(await self.contributors)) - 1)
        self._collaborators = self.environment_vars.more_collaborators + collaborators
        return self._collaborators

    @property
    async def contributors(self) -> Set:
        """
        :return: count of total contributors to user's repositories
        """
        if self._contributors is not None:
            return self._contributors
        await self.lines_changed
        assert self._contributors is not None
        return self._contributors

    @property
    async def pull_requests(self) -> int:
        """
        :return: count of pull requests in repos user has either created, reviewed, commented, been assigned...
        """
        if self._pull_requests is not None:
            return self._pull_requests

        pull_requests = set()

        if not self._is_fetch_rate_limit_exceeded:
            for repo in await self.repos:
                end_point = f"/repos/{repo}/pulls?state=all&involved={self.environment_vars.username}"

                for pr_data in await self.queries.query_rest(end_point):
                    try:
                        pull_requests.add(
                            pr_data["url"]
                        ) if "url" in pr_data.keys() else None
                    except AttributeError:
                        self._is_fetch_rate_limit_exceeded = True
                        break

                if self._is_fetch_rate_limit_exceeded:
                    break

        self._pull_requests = (
            len(pull_requests)
            if len(pull_requests) > self.environment_vars.pull_requests_count
            else self.environment_vars.pull_requests_count
        )
        self.environment_vars.set_pull_requests(self._pull_requests)
        return self._pull_requests

    @property
    async def issues(self) -> int:
        """
        :return: count of issues in repos user has either created, reacted to, commented, been assigned...
        """
        if self._issues is not None:
            return self._issues

        issues = set()

        if not self._is_fetch_rate_limit_exceeded:
            for repo in await self.repos:
                end_point = f"/repos/{repo}/issues?state=all&involved={self.environment_vars.username}"

                for issue_data in await self.queries.query_rest(end_point):
                    try:
                        issues.add(
                            issue_data["url"]
                        ) if "url" in issue_data.keys() else None
                    except AttributeError:
                        self._is_fetch_rate_limit_exceeded = True
                        break

                if self._is_fetch_rate_limit_exceeded:
                    break

        self._issues = (
            len(issues)
            if len(issues) > self.environment_vars.issues_count
            else self.environment_vars.issues_count
        )
        self.environment_vars.set_issues(self._issues)
        return self._issues
