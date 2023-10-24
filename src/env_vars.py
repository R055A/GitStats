#!/usr/bin/python3

from os import getenv, environ
from typing import Optional
from datetime import datetime

from src.db.db import GitRepoStatsDB

###############################################################################
# EnvironmentVariables class - uses GitRepoStatsDB class as second resort
###############################################################################


class EnvironmentVariables:
    __DATE_FORMAT = "%Y-%m-%d"

    def __init__(
        self,
        username: str,
        access_token: str,
        exclude_repos: Optional[str] = getenv("EXCLUDED"),
        exclude_langs: Optional[str] = getenv("EXCLUDED_LANGS"),
        include_forked_repos: str = getenv("INCLUDE_FORKED_REPOS"),
        exclude_contrib_repos: str = getenv("EXCLUDE_CONTRIB_REPOS"),
        exclude_archive_repos: str = getenv("EXCLUDE_ARCHIVE_REPOS"),
        exclude_private_repos: str = getenv("EXCLUDE_PRIVATE_REPOS"),
        exclude_public_repos: str = getenv("EXCLUDE_PUBLIC_REPOS"),
        repo_views: Optional[str] = getenv("REPO_VIEWS"),
        repo_last_viewed: Optional[str] = getenv("LAST_VIEWED"),
        repo_first_viewed: Optional[str] = getenv("FIRST_VIEWED"),
        store_repo_view_count: str = getenv("STORE_REPO_VIEWS"),
        more_collaborators: Optional[str] = getenv("MORE_COLLABS"),
        manually_added_repos: Optional[str] = getenv("MORE_REPOS"),
        only_included_repos: Optional[str] = getenv("ONLY_INCLUDED"),
        exclude_collab_repos: Optional[str] = getenv("EXCLUDED_COLLAB_REPOS"),
        more_collab_repos: Optional[str] = getenv("MORE_COLLAB_REPOS"),
    ):
        self.__db = GitRepoStatsDB()

        self.username = username
        self.access_token = access_token

        if exclude_repos is None:
            self.exclude_repos = set()
        else:
            self.exclude_repos = {x.strip() for x in exclude_repos.split(",")}

        if exclude_langs is None:
            self.exclude_langs = set()
        else:
            self.exclude_langs = {x.strip() for x in exclude_langs.split(",")}

        self.include_forked_repos = (
            not not include_forked_repos
            and include_forked_repos.strip().lower() == "true"
        )

        self.exclude_contrib_repos = (
            not not exclude_contrib_repos
            and exclude_contrib_repos.strip().lower() == "true"
        )

        self.exclude_archive_repos = (
            not not exclude_archive_repos
            and exclude_archive_repos.strip().lower() == "true"
        )

        self.exclude_private_repos = (
            not not exclude_private_repos
            and exclude_private_repos.strip().lower() == "true"
        )

        self.exclude_public_repos = (
            not not exclude_public_repos
            and exclude_public_repos.strip().lower() == "true"
        )

        self.store_repo_view_count = (
            not store_repo_view_count
            or store_repo_view_count.strip().lower() != "false"
        )

        if self.store_repo_view_count:
            try:
                if repo_views:
                    self.repo_views = int(repo_views)
                    self.__db.set_views_count(self.repo_views)
                else:
                    self.repo_views = self.__db.views
            except ValueError:
                self.repo_views = self.__db.views

            if repo_last_viewed:
                try:
                    if repo_last_viewed == datetime.strptime(
                        repo_last_viewed, self.__DATE_FORMAT
                    ).strftime(self.__DATE_FORMAT):
                        self.repo_last_viewed = repo_last_viewed
                except ValueError:
                    self.repo_last_viewed = self.__db.views_to_date
            else:
                self.repo_last_viewed = self.__db.views_to_date

            if repo_first_viewed:
                try:
                    if repo_first_viewed == datetime.strptime(
                        repo_first_viewed, self.__DATE_FORMAT
                    ).strftime(self.__DATE_FORMAT):
                        self.repo_first_viewed = repo_first_viewed
                except ValueError:
                    self.repo_first_viewed = self.__db.views_from_date
            else:
                self.repo_first_viewed = self.__db.views_from_date

        else:
            self.repo_views = 0
            self.__db.set_views_count(self.repo_views)
            self.repo_last_viewed = "0000-00-00"
            self.repo_first_viewed = "0000-00-00"
            self.__db.set_views_from_date(self.repo_first_viewed)
            self.__db.set_views_to_date(self.repo_last_viewed)

        try:
            self.more_collaborators = (
                int(more_collaborators) if more_collaborators else 0
            )
        except ValueError:
            self.more_collaborators = 0

        if manually_added_repos is None:
            self.manually_added_repos = set()
        else:
            self.manually_added_repos = {
                x.strip() for x in manually_added_repos.split(",")
            }

        if only_included_repos is None or only_included_repos == "":
            self.only_included_repos = set()
        else:
            self.only_included_repos = {
                x.strip() for x in only_included_repos.split(",")
            }

        if exclude_collab_repos is None:
            self.exclude_collab_repos = set()
        else:
            self.exclude_collab_repos = {
                x.strip() for x in exclude_collab_repos.split(",")
            }

        if more_collab_repos is None:
            self.more_collab_repos = set()
        else:
            self.more_collab_repos = {x.strip() for x in more_collab_repos.split(",")}

        self.pull_requests_count = self.__db.pull_requests
        self.issues_count = self.__db.issues

    def set_views(self, views: any) -> None:
        self.repo_views += int(views)
        environ["REPO_VIEWS"] = str(self.repo_views)
        self.__db.set_views_count(self.repo_views)

    def set_last_viewed(self, new_last_viewed_date: str) -> None:
        self.repo_last_viewed = new_last_viewed_date
        environ["LAST_VIEWED"] = self.repo_last_viewed
        self.__db.set_views_to_date(self.repo_last_viewed)

    def set_first_viewed(self, new_first_viewed_date: str) -> None:
        self.repo_first_viewed = new_first_viewed_date
        environ["FIRST_VIEWED"] = self.repo_first_viewed
        self.__db.set_views_from_date(self.repo_first_viewed)

    def set_pull_requests(self, pull_requests_count: int) -> None:
        self.__db.pull_requests = pull_requests_count

    def set_issues(self, issues_count: int) -> None:
        self.__db.issues = issues_count
