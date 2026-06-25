import json
import logging
import os
import platform
import subprocess

import psutil
import requests

arrow_bci_url = os.getenv("ARROW_BCI_URL")
arrow_bci_api_access_token = os.getenv("ARROW_BCI_API_ACCESS_TOKEN")
logging.basicConfig(level=logging.INFO)


def context():
    if not os.getenv("BENCHMARKABLE_TYPE") in ["arrow-commit", "pyarrow-apache-wheel"]:
        return

    import pyarrow

    build_info = pyarrow.cpp_build_info
    return {
        "arrow_compiler_id": build_info.compiler_id,
        "arrow_compiler_version": build_info.compiler_version,
        "arrow_compiler_flags": build_info.compiler_flags,
    }


def machine_info():
    return {
        "name": os.getenv("MACHINE") or platform.node(),
        "architecture": platform.machine(),
        "cpu_count": os.cpu_count(),
        "memory_bytes": psutil.virtual_memory().total,
        "os_name": platform.system(),
        "os_version": platform.release(),
    }


def conda_packages():
    result = subprocess.run(["conda", "list", "-e"], stdout=subprocess.PIPE)
    return result.stdout.decode()


def run_context():
    return {
        "context": context(),
        "machine_info": machine_info(),
        "conda_packages": conda_packages(),
    }


def post_logs_to_arrow_bci(url, data):
    if not arrow_bci_url or not arrow_bci_api_access_token:
        return

    try:
        requests.post(
            f"{arrow_bci_url}/{url}",
            data=json.dumps(data),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {arrow_bci_api_access_token}",
            },
        )
    except Exception as e:
        logging.exception(f"Failed to post to {url}: {data}")
        logging.exception(e)
