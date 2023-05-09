#!/usr/bin/python3

from asyncio import run, gather
from aiohttp import ClientSession
from os import mkdir, getenv
from os.path import isdir
from re import sub

from src.env_vars import EnvironmentVariables
from src.github_repo_stats import GitHubRepoStats

OUTPUT_DIR = "generated_images"  # directory for storing generated images
TEMPLATE_PATH = "src/templates/"
OVERVIEW_FILE_NAME = "overview.svg"
LANGUAGES_FILE_NAME = "languages.svg"
TXT_SPACER_MAX_LEN = 7
MAX_NAME_LEN = 18


###############################################################################
# Helper Functions
###############################################################################

def generate_output_folder() -> None:
    """
    Create the output folder if it does not already exist
    """
    if not isdir(OUTPUT_DIR):
        mkdir(OUTPUT_DIR)

###############################################################################
# GenerateImages class
###############################################################################


class GenerateImages:

    def __init__(self):
        access_token = getenv("ACCESS_TOKEN")
        user = getenv("GITHUB_ACTOR")

        if not access_token:
            raise Exception("A personal access token is required to proceed!")

        if not user:
            raise RuntimeError("Environment variable GITHUB_ACTOR must be set")

        self.__environment = EnvironmentVariables(username=user,
                                                  access_token=access_token)
        self.__stats = None

        run(self.start())

    async def start(self) -> None:
        """
        Main function: generate all badges
        """
        async with ClientSession() as session:
            self.__stats = GitHubRepoStats(environment_vars=self.__environment,
                                           session=session)
            await gather(self.generate_languages(),
                         self.generate_overview())

    async def generate_overview(self) -> None:
        """
        Generate an SVG badge with summary statistics
        """
        with open("{}{}".format(TEMPLATE_PATH,
                                OVERVIEW_FILE_NAME), "r") as f:
            output = f.read()

        name = await self.__stats.name
        if len(name + ("'" if name[-1].lower() == "s" else "'s")) > MAX_NAME_LEN:
            names = name.split(' ')
            if len(names) == 1 or len(names[0][0] + '. ' + names[-1] +
                                      ("'" if names[-1][-1].lower() == "s" else "'s")) > MAX_NAME_LEN:
                if self.__stats.environment_vars.username + \
                       ("'" if self.__stats.environment_vars.username[-1].lower() == "s" else "'s") > MAX_NAME_LEN:
                    name = self.__stats.environment_vars.username + \
                           ("'" if self.__stats.environment_vars.username[-1].lower() == "s" else "'s")
                else:
                    name = ' '.join([name[0] + '.' for name in names])
                    name = name.strip()[:min(len(name), MAX_NAME_LEN - 2)] + "'s"
            else:
                name = names[0][0] + '. ' + names[-1] + ("'" if names[-1][-1].lower() == "s" else "'s")
        else:
            name += "'" if name[-1].lower() == "s" else "'s"
        output = sub("{{ name }}",
                     name,
                     output)

        views = f"{await self.__stats.views:,}"
        output = sub("{{ views }}",
                     views,
                     output)

        forks = f"{await self.__stats.forks:,}"
        stars = f"{await self.__stats.stargazers:,}"
        forks_and_stars = \
            forks + ' ' * max(1, TXT_SPACER_MAX_LEN - len(str(forks)) + 1) + '|   ' + stars
        output = sub("{{ forks_and_stars }}",
                     forks_and_stars,
                     output)

        contributions = f"{await self.__stats.total_contributions:,}"
        output = sub("{{ contributions }}",
                     contributions,
                     output)

        changed = (await self.__stats.lines_changed)[0] + \
                  (await self.__stats.lines_changed)[1]
        output = sub("{{ lines_changed }}",
                     f"{changed:,}",
                     output)

        avg_contribution_percent = await self.__stats.avg_contribution_percent
        output = sub("{{ avg_contribution_percent }}",
                     avg_contribution_percent,
                     output)

        repos = f"{len(await self.__stats.repos):,}"
        output = sub("{{ repos }}",
                     repos,
                     output)

        collaborators_and_contributors = f"{await self.__stats.collaborators:,}"
        output = sub("{{ collaborators_and_contributors }}",
                     collaborators_and_contributors,
                     output)

        views_from = (await self.__stats.views_from_date)
        output = sub("{{ views_from_date }}",
                     f"Repo views (as of {views_from})",
                     output)

        pull_requests = f"{await self.__stats.pull_requests:,}"
        issues = f"{await self.__stats.issues:,}"
        pull_requests_and_issues = \
            pull_requests + ' ' * max(1, TXT_SPACER_MAX_LEN - len(str(pull_requests)) + 1) + '|   ' + issues
        output = sub("{{ pull_requests_and_issues }}",
                     pull_requests_and_issues,
                     output)

        generate_output_folder()
        with open("{}/{}".format(OUTPUT_DIR,
                                 OVERVIEW_FILE_NAME), "w") as f:
            f.write(output)

    async def generate_languages(self) -> None:
        """
        Generate an SVG badge with summary languages used
        """
        with open("{}{}".format(TEMPLATE_PATH,
                                LANGUAGES_FILE_NAME), "r") as f:
            output = f.read()

        progress = ""
        lang_list = ""
        sorted_languages = sorted((await self.__stats.languages).items(),
                                  reverse=True,
                                  key=lambda t: t[1].get("size"))

        lang_count = str(len(sorted_languages))
        num_excluded_languages = len(await self.__stats.excluded_languages)
        if num_excluded_languages > 0:
            lang_count += ' [+' + str(num_excluded_languages) + ']'

        delay_between = 150

        for i, (lang, data) in enumerate(sorted_languages):
            color = data.get("color")
            color = color if color is not None else "#000000"
            progress += (f'<span style="background-color: {color};'
                         f'width: {data.get("prop", 0):0.5f}%;" '
                         f'class="progress-item"></span>')
            lang_list += f"""
            <li style="animation-delay: {i * delay_between}ms;">
                    <svg xmlns="http://www.w3.org/2000/svg" 
                         class="octicon" 
                         style="fill:{color};"
                         viewBox="0 0 16 16" 
                         version="1.1" 
                         width="16" 
                         height="16">
                            <path fill-rule="evenodd" 
                                  d="M8 4a4 4 0 100 8 4 4 0 000-8z">
                            </path>
                    </svg>
                    <span class="lang">
                        {lang}
                    </span>
                    <span class="percent">
                        {data.get("prop", 0):0.2f}%
                    </span>
            </li>"""

        output = sub(r"{{ lang_count }}",
                     lang_count,
                     output)

        output = sub(r"{{ progress }}",
                     progress,
                     output)

        output = sub(r"{{ lang_list }}",
                     lang_list,
                     output)

        generate_output_folder()
        with open("{}/{}".format(OUTPUT_DIR,
                                 LANGUAGES_FILE_NAME), "w") as f:
            f.write(output)
