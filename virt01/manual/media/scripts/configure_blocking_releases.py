#!/usr/bin/env python3
import argparse
import json
import os
import ssl
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


CUSTOM_FORMAT_NAME = "Block Malware and Banned Release Terms"
LEGACY_CUSTOM_FORMAT_NAMES = {"Block .EXE / .SCR Malware"}
BLOCKING_REGEX = (
    r"(?i)(?:^|[ ._-])(?:cam(?:[ ._-]*rip)?|tele[ ._-]*cine|tele[ ._-]*sync|"
    r"successfulcrab|screenerdvdscr|dvd[ ._-]*scr|hdtcworkprint|dvd[ ._-]*iso|"
    r"bd[ ._-]*scr|bd[ ._-]*iso|hd[ ._-]*cam|cc[ ._-]*hd|hd[ ._-]*tc|"
    r"dvd[ ._-]*r|hd[ ._-]*ts|workprint|screener|preview|torrent|trailer|"
    r"dvdscr|teaser|sample|hdcam|mhtml|bdscr|xlsm|sldx|zipx|html|docm|ppam|"
    r"potx|pptm|ppsx|psd1|psm1|xltm|xlam|bash|potm|sldm|xlsb|jse|dll|rar|"
    r"cmd|tcl|bas|mht|adp|pif|ins|key|mda|vbs|msi|jar|isp|hta|mdw|ocx|hlp|"
    r"ps2|lnk|wsf|bin|zip|ipa|apk|nsh|drv|tmp|com|chm|wsh|exe|bz2|php|crt|"
    r"iso|bat|ade|scr|msp|mdb|mdt|mdz|tgz|zst|vbe|scf|ps1|dmg|app|sys|cpl|"
    r"tar|img|vxd|vb|js|r6|gz|xz|tc|wp|py|r5|sh|7z)(?:$|[ ._-])"
)

RELEASE_TERM_PATTERNS = [
    r"/\b(?:DVDR|DVD-?R|DVD-?ISO|BDISO)\b/i",
    r"/\b(?:sample|trailer|preview|teaser|successfulcrab)\b/i",
    r"/\b(?:CAM(?:-?RIP)?|TS|TELE-?SYNC|TC|TELE-?CINE|HD-?CAM|SCR|SCREENER|DVD-?SCR|BD-?SCR|WORKPRINT|WP|R5|R6|HD-?TS|HD-?TC)\b/i",
]

NON_MEDIA_TERMS = [
    ".lnk",
    ".zipx",
    "sample.mkv",
    "sample.avi",
    "sample.mp4",
    ".py",
    ".vbs",
    ".html",
    ".php",
    ".torrent",
    ".exe",
    ".bat",
    ".cmd",
    ".com",
    ".cpl",
    ".dll",
    ".js",
    ".jse",
    ".msi",
    ".msp",
    ".pif",
    ".scr",
    ".vbe",
    ".wsf",
    ".wsh",
    ".hta",
    ".reg",
    ".inf",
    ".ps1",
    ".ps2",
    ".psm1",
    ".psd1",
    ".sh",
    ".apk",
    ".app",
    ".ipa",
    ".iso",
    ".jar",
    ".bin",
    ".tmp",
    ".vb",
    ".vxd",
    ".ocx",
    ".drv",
    ".sys",
    ".scf",
    ".ade",
    ".adp",
    ".bas",
    ".chm",
    ".crt",
    ".hlp",
    ".ins",
    ".isp",
    ".key",
    ".mda",
    ".mdb",
    ".mdt",
    ".mdw",
    ".mdz",
    ".potm",
    ".potx",
    ".ppam",
    ".ppsx",
    ".pptm",
    ".sldm",
    ".sldx",
    ".xlam",
    ".xlsb",
    ".xlsm",
    ".xltm",
    ".nsh",
    ".mht",
    ".mhtml",
    ".img",
    ".dmg",
    ".docm",
]

RELEASE_PROFILES = [
    {"name": "Banned - release terms", "ignored": RELEASE_TERM_PATTERNS},
    {"name": "Banned - non-media extensions", "ignored": NON_MEDIA_TERMS},
]


class ArrApi:
    def __init__(self, base_url: str, token: str, ssl_context: ssl.SSLContext):
        self.base_url = base_url.rstrip("/") + "/"
        self.token = token
        self.ssl_context = ssl_context

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"X-Api-Key": self.token, "Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"

        request = Request(
            urljoin(self.base_url, path.lstrip("/")),
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, context=self.ssl_context, timeout=30) as response:
                content = response.read()
        except HTTPError as error:
            raise RuntimeError(f"{method} {path} failed with HTTP {error.code}") from error
        except URLError as error:
            raise RuntimeError(f"{method} {path} failed: {error.reason}") from error

        if not content:
            return None
        try:
            return json.loads(content)
        except json.JSONDecodeError as error:
            raise RuntimeError(f"{method} {path} returned invalid JSON") from error


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, separator, value = line.partition("=")
        if not separator:
            raise ValueError(f"{path}:{line_number}: expected KEY=VALUE")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key.strip()] = value
    return values


def load_settings(env_file: Path | None) -> dict[str, str]:
    settings = read_env_file(env_file.expanduser()) if env_file else {}
    settings.update(os.environ)
    return settings


def get_ssl_context(settings: dict[str, str]) -> ssl.SSLContext:
    ca_file = settings.get("SSL_CERT_FILE")
    if ca_file and not Path(ca_file).is_file():
        raise ValueError(f"SSL_CERT_FILE does not point to a readable file: {ca_file}")
    return ssl.create_default_context(cafile=ca_file or None)


def find_named(
    resources: list[dict[str, Any]], names: set[str], resource_type: str
) -> dict[str, Any] | None:
    matches = [resource for resource in resources if resource.get("name") in names]
    if len(matches) > 1:
        raise RuntimeError(f"Found multiple {resource_type} resources with managed names")
    return matches[0] if matches else None


def desired_custom_format(existing: dict[str, Any] | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "name": CUSTOM_FORMAT_NAME,
        "includeCustomFormatWhenRenaming": False,
        "specifications": [
            {
                "name": "block",
                "implementation": "ReleaseTitleSpecification",
                "negate": False,
                "required": False,
                "fields": [{"name": "value", "value": BLOCKING_REGEX}],
            }
        ],
    }
    if existing and existing.get("id") is not None:
        result["id"] = existing["id"]
    return result


def custom_format_is_configured(resource: dict[str, Any]) -> bool:
    if resource.get("name") != CUSTOM_FORMAT_NAME:
        return False
    if resource.get("includeCustomFormatWhenRenaming") is not False:
        return False
    specifications = resource.get("specifications") or []
    if len(specifications) != 1:
        return False
    specification = specifications[0]
    fields = specification.get("fields") or []
    return (
        specification.get("name") == "block"
        and specification.get("implementation") == "ReleaseTitleSpecification"
        and specification.get("negate") is False
        and specification.get("required") is False
        and len(fields) == 1
        and fields[0].get("name") == "value"
        and fields[0].get("value") == BLOCKING_REGEX
    )


def release_profile_payload(
    app: str, definition: dict[str, Any], existing: dict[str, Any] | None = None
) -> dict[str, Any]:
    payload = dict(existing or {})
    payload.update(
        {
            "name": definition["name"],
            "enabled": True,
            "required": [],
            "ignored": definition["ignored"],
            "indexerId": 0,
            "tags": [],
        }
    )
    if app == "SONARR":
        payload["excludedTags"] = []
    return payload


def release_profile_is_configured(
    resource: dict[str, Any], definition: dict[str, Any]
) -> bool:
    return (
        resource.get("name") == definition["name"]
        and resource.get("enabled") is True
        and resource.get("required") == []
        and resource.get("ignored") == definition["ignored"]
        and resource.get("indexerId") == 0
        and resource.get("tags") in (None, [])
        and resource.get("excludedTags") in (None, [])
    )


def profile_score(profile: dict[str, Any], format_id: int) -> int | None:
    matches = [
        item
        for item in profile.get("formatItems", [])
        if item.get("format") == format_id
    ]
    if len(matches) > 1:
        raise RuntimeError(
            f"Quality profile {profile.get('name')} has duplicate entries for the blocking Custom Format"
        )
    return matches[0].get("score") if matches else None


def set_profile_score(
    client: ArrApi, profile: dict[str, Any], format_id: int, apply: bool
) -> bool:
    current_score = profile_score(profile, format_id)
    if current_score == -9999:
        return False
    if not apply:
        return True

    payload = dict(profile)
    items = list(payload.get("formatItems") or [])
    existing = next(
        (item for item in items if item.get("format") == format_id), None
    )
    if existing:
        existing["score"] = -9999
    else:
        items.append({"format": format_id, "score": -9999})
    payload["formatItems"] = items
    client.request("PUT", f"api/v3/qualityprofile/{profile['id']}", payload)
    return True


def require_list(value: Any, description: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise RuntimeError(f"Unexpected {description} response from Arr API")
    return value


def reconcile_app(app: str, settings: dict[str, str], ssl_context: ssl.SSLContext, apply: bool) -> None:
    base_url = settings.get(f"{app}_BASE_URL")
    token = settings.get(f"{app}_TOKEN")
    if not base_url or not token:
        raise ValueError(f"{app}_BASE_URL and {app}_TOKEN are required")
    client = ArrApi(base_url, token, ssl_context)

    formats = require_list(client.request("GET", "api/v3/customformat"), "Custom Format collection")
    profiles = require_list(client.request("GET", "api/v3/qualityprofile"), "Quality Profile collection")
    releases = require_list(client.request("GET", "api/v3/releaseprofile"), "Release Profile collection")
    if not profiles:
        raise RuntimeError(f"{app} has no Quality Profiles; create one before applying blocking rules")

    candidates = {CUSTOM_FORMAT_NAME} | LEGACY_CUSTOM_FORMAT_NAMES
    current_format = find_named(formats, candidates, "Custom Format")
    format_ok = current_format is not None and custom_format_is_configured(current_format)
    format_id = current_format.get("id") if current_format else None

    print(f"{app}:")
    if format_ok:
        print(f"  Custom Format: already configured (id {format_id})")
    else:
        action = "create" if current_format is None else "update"
        print(f"  Custom Format: {action} {CUSTOM_FORMAT_NAME}")

    score_changes = (
        len(profiles)
        if format_id is None
        else sum(profile_score(profile, format_id) != -9999 for profile in profiles)
    )
    if score_changes:
        print(f"  Quality Profiles: set score -9999 in {score_changes} of {len(profiles)} profiles")
    else:
        print(f"  Quality Profiles: blocking score already set in all {len(profiles)} profiles")

    profile_resources = []
    for definition in RELEASE_PROFILES:
        existing = find_named(releases, {definition["name"]}, "Release Profile")
        profile_resources.append((definition, existing))
        if existing and release_profile_is_configured(existing, definition):
            print(f"  Release Profile: already configured ({definition['name']})")
        else:
            action = "create" if existing is None else "update"
            print(f"  Release Profile: {action} {definition['name']}")

    if not apply:
        return

    if not format_ok:
        payload = desired_custom_format(current_format)
        if current_format is None:
            client.request("POST", "api/v3/customformat", payload)
        else:
            client.request("PUT", f"api/v3/customformat/{current_format['id']}", payload)

    formats = require_list(client.request("GET", "api/v3/customformat"), "Custom Format collection")
    managed_format = find_named(formats, {CUSTOM_FORMAT_NAME}, "Custom Format")
    if not managed_format or not custom_format_is_configured(managed_format):
        raise RuntimeError(f"{app} Custom Format failed read-back verification")
    format_id = managed_format.get("id")
    if not isinstance(format_id, int):
        raise RuntimeError(f"{app} Custom Format returned an invalid ID")

    for profile in profiles:
        set_profile_score(client, profile, format_id, apply=True)

    for definition, existing in profile_resources:
        if existing and release_profile_is_configured(existing, definition):
            continue
        payload = release_profile_payload(app, definition, existing)
        if existing is None:
            client.request("POST", "api/v3/releaseprofile", payload)
        else:
            client.request("PUT", f"api/v3/releaseprofile/{existing['id']}", payload)

    verified_profiles = require_list(
        client.request("GET", "api/v3/qualityprofile"), "Quality Profile collection"
    )
    for profile in verified_profiles:
        if profile_score(profile, format_id) != -9999:
            raise RuntimeError(f"{app} failed score verification for profile {profile.get('name')}")

    verified_releases = require_list(
        client.request("GET", "api/v3/releaseprofile"), "Release Profile collection"
    )
    for definition in RELEASE_PROFILES:
        resource = find_named(verified_releases, {definition["name"]}, "Release Profile")
        if not resource or not release_profile_is_configured(resource, definition):
            raise RuntimeError(f"{app} failed read-back verification for {definition['name']}")
    print(f"  Verified: Custom Format score and both Release Profiles")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create or reconcile the malware and banned-title rules in Sonarr and Radarr."
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        help="Optional KEY=VALUE file with Arr URLs, API tokens, and SSL_CERT_FILE",
    )
    parser.add_argument(
        "--app",
        choices=("both", "sonarr", "radarr"),
        default="both",
        help="Which Arr app to configure (default: both)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes; without this flag the script only reads and reports planned changes",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        settings = load_settings(args.env_file)
        ssl_context = get_ssl_context(settings)
        apps = ("SONARR", "RADARR") if args.app == "both" else (args.app.upper(),)
        for app in apps:
            reconcile_app(app, settings, ssl_context, args.apply)
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    if not args.apply:
        print("Dry run only. Pass --apply to create or update these settings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
