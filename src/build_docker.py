"""
This module facilitates the building of the docker images associated with each repo.
"""

import docker
import argparse
import os
from multiprocessing import Pool

BASE_DIR = "data"


def get_args() -> argparse.Namespace:
    """
    Parse commandline arguments.
    :returns: Namespace containing the supplied arguments.
    """
    parser = argparse.ArgumentParser(
        prog="build_docker",
        description="Attempt to build dockerfiles. Images will be tagged as {repo_owner}/{repo_name}.",
    )

    parser.add_argument("-o", "--repo-owner", help="The name of the repo owner.")
    parser.add_argument("-n", "--repo-name", help="The name of the repo.")
    parser.add_argument(
        "-t", "--threads", help="The number of threads to execute in parallel. Defaults to serial.", type=int
    )

    args = parser.parse_args()

    if bool(args.repo_owner) != bool(args.repo_name):
        parser.error(
            "The --repo_owner and --repo_name arguments must be supplied together (or both left blank to build all "
            "docker images)."
        )
    return args


def build_image(repo_owner: str, repo_name: str) -> docker.models.images.Image:
    """
    Build the docker image corresponding to the supplied repo.
    """
    client = docker.from_env()
    image, build_logs = client.images.build(
        path=os.path.join(BASE_DIR, repo_owner, repo_name),
        tag=f"{repo_owner.lower()}:{repo_name.lower()}",
        rm=True,  # Remove intermediate containers after a successful build
    )

    for line in build_logs:
        if "stream" in line:
            print(line["stream"].strip())
    return image


def main():
    """
    Main entrypoint.
    """
    args = get_args()
    if args.repo_owner and args.repo_name:
        repos = {args.repo_owner: [args.repo_name]}
    else:
        repos = {repo_owner: os.listdir(os.path.join(BASE_DIR, repo_owner)) for repo_owner in os.listdir(BASE_DIR)}

    if args.threads:
        with Pool(args.threads) as pool:
            pool.starmap(
                build_image,
                [(repo_owner, repo_name) for repo_name in repo_names for repo_owner, repo_names in repos.items()],
            )

    else:
        for repo_owner, repo_names in repos.items():
            for repo_name in repo_names:
                build_image(repo_owner, repo_name)


if __name__ == "__main__":
    main()
