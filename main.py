# My idea: read registry, expose `$API/registry/`, with `$API/registry/component.raw` or whateve dependingo n the tag

# Example:
# Path=http://localhost:6767/ghcr.io_tulilirockz_zirconium/ # this would have valid! (usr-VERSION-WHATEVER.raw) files based off of tags in the registry itself
# Path=https://1270333429.rsc.cdn77.org/nightly/sysupdate/
# MatchPattern=gnomeos-nvidia-%a_@v.addon.efi gnomeos-nvidia-%a_@v.addon.efi.xz

# Get the URL (ghcr.io/tulilirockz/zirconium/usr:latest), resolve to blob, oras blob fetch to file descriptor. bam done
import os
import platform
import json
import subprocess
from venv import logger
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, StreamingResponse
import logging

logger = logging.getLogger(__name__)
ARBITRARY_BYTES_VALUE_IDK = 5000

app = FastAPI()

def run_with_log(logger: Logger, args: list[str]) -> subprocess.CompletedProcess[bytes]:
    logger.debug(f"Running external command: {args}")
    return subprocess.run(args, capture_output=True)

def select_artifact(manifest_config: str, filter_func: function = lambda x : x) -> str:
    return filter(filter_func, manifest_config["layers"])[0]["digest"]

def fetch_manifest(logger: Logger, registry_image: str, architecture: str = platform.uname().machine) -> str:
    github_architecture = architecture.replace("x86_", "amd").replace("arm", "aarch")
    logger.debug(f"Selected architecture is: {github_architecture}")
    manifest = run_with_log(logger, ["oras", "manifest", "fetch", registry_image, "--platform", f"linux/{github_architecture}"])
    if manifest.stdout == b'':
        manifest = run_with_log(logger, ["oras", "manifest", "fetch", registry_image])
    if manifest.stdout == b'':
        logger.warn("FIXME: Manifest failed to be fetched!")
    logger.debug(f"Manifest found: {manifest.stdout}")
    return manifest.stdout

@app.get('/{_:path}', response_class=StreamingResponse)
def main(request: Request):
    logging.basicConfig(level=logging.DEBUG)
    architecture_uname_raw = platform.uname().machine

    target_image_base = os.environ.get("TARGET_IMAGE_BASE", "localhost:5005")
    if request.url.path[1:] == "SHA256SUMS":
        target_image = f"{target_image_base}/{request.url.path[1:].lower()}:latest" 
        logger.debug(f"Target image: {target_image}")

        manifest_config = json.loads(fetch_manifest(logger, target_image, architecture=architecture_uname_raw))
        selected_artifact = manifest_config["layers"][0]["digest"]
        logger.debug(f"Artifact: {selected_artifact}")

        with subprocess.Popen(["oras", "blob", "fetch", f"{target_image_base}/{request.url.path[1:].lower()}@{selected_artifact}", "--no-tty", "-o", "/dev/stdout"], stdout=subprocess.PIPE, bufsize=1) as process:
            while True:
                c = process.stdout.read(ARBITRARY_BYTES_VALUE_IDK)
                if not c:
                    break
                yield c

        return

    registry_image = request.url.path[1:] if not request.url.query else request.url.path[1:] + "?" + request.url.query

    # We need to figure out how to remove the md5? hash from the outputs
    # systemd_formatted_arch = architecture_uname_raw.replace("_", "-")
    # filter_image = lambda x: x["annotations"]["org.opencontainers.image.title"] == f"Zirconium_20260708005028_{systemd_formatted_arch}.usr-{systemd_formatted_arch}.6e3a4113bb8b6d1eebf5e0df64e5328e.raw" 

    manifest_config = json.loads(fetch_manifest(logger, registry_image, architecture=architecture_uname_raw))
    selected_artifact = manifest_config["layers"][0]["digest"]

    with subprocess.Popen(["oras", "blob", "fetch", f"{registry_image}@{selected_artifact}", "--no-tty", "-o", "/dev/stdout"], stdout=subprocess.PIPE, bufsize=1) as process:
        while True:
            c = process.stdout.read(ARBITRARY_BYTES_VALUE_IDK)
            if not c:
                break
            yield c
