from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib.request import urlopen

from django.core.management.base import BaseCommand
from django.db import transaction

from locations.models import LocationNode


@dataclass(frozen=True)
class SourceUrls:
    provinces: str
    districts: str
    local_levels: str
    local_level_types: Optional[str] = None


BIBEKOLI = SourceUrls(
    provinces="https://raw.githubusercontent.com/bibekoli/local-levels-of-nepal-dataset/main/provinces.json",
    districts="https://raw.githubusercontent.com/bibekoli/local-levels-of-nepal-dataset/main/districts.json",
    local_levels="https://raw.githubusercontent.com/bibekoli/local-levels-of-nepal-dataset/main/local_levels.json",
    local_level_types="https://raw.githubusercontent.com/bibekoli/local-levels-of-nepal-dataset/main/local_level_type.json",
)

# If you prefer sagautam5, you can add a second mapping here once you pick exact dataset file paths.
# It is MIT licensed and supports English/नेपाली out of the box. (See repository)  # noqa


def _fetch_json(url: str) -> Any:
    with urlopen(url) as fp:
        return json.loads(fp.read().decode("utf-8"))


def _pid(pid: int) -> str:
    return f"NP-P{pid}"


def _did(pid: int, did: int) -> str:
    # did is global in dataset; still deterministic. Add pid to avoid collisions if you ever switch source.
    return f"NP-P{pid}-D{did:02d}"


def _llid(pid: int, did: int, llid: int) -> str:
    return f"NP-P{pid}-D{did:02d}-LL{llid:04d}"


def _category_from_type(type_name_en: str) -> str:
    """
    Normalize dataset types to your meta.local_level_category.
    """
    t = (type_name_en or "").strip().lower()
    if "metropolitan" in t and "sub" not in t:
        return "METROPOLITAN"
    if "sub" in t and "metropolitan" in t:
        return "SUB_METROPOLITAN"
    if "rural" in t:
        return "RURAL_MUNICIPALITY"
    return "MUNICIPALITY"


class Command(BaseCommand):
    help = "Import Nepal admin hierarchy (provinces, districts, local levels) into LocationNode."

    def add_arguments(self, parser):
        parser.add_argument("--source", default="bibekoli", choices=["bibekoli"])
        parser.add_argument("--dry-run", action="store_true")

    @transaction.atomic
    def handle(self, *args, **opts):
        dry_run: bool = opts["dry_run"]
        src = BIBEKOLI

        provinces = _fetch_json(src.provinces)
        districts = _fetch_json(src.districts)
        local_levels = _fetch_json(src.local_levels)

        type_map: Dict[int, Tuple[str, str]] = {}
        if src.local_level_types:
            types = _fetch_json(src.local_level_types)
            # Example: { "local_level_type_id": 1, "name": "...", "nepali_name": "..." }
            for t in types:
                type_map[int(t["local_level_type_id"])] = (t["name"], t.get("nepali_name", ""))

        # Ensure country exists
        LocationNode.objects.update_or_create(
            id="NP",
            defaults=dict(
                type=LocationNode.Type.COUNTRY,
                name_en="Nepal",
                name_np="नेपाल",
                code="NP",
                parent=None,
                is_active=True,
                aliases_en=[],
                aliases_np=[],
                meta={},
            ),
        )

        # Provinces
        for p in provinces:
            pid = int(p["province_id"])
            LocationNode.objects.update_or_create(
                id=_pid(pid),
                defaults=dict(
                    type=LocationNode.Type.PROVINCE,
                    name_en=p["name"],
                    name_np=p.get("nepali_name", ""),
                    code=f"P{pid}",
                    parent_id="NP",
                    is_active=True,
                    meta={"source": "bibekoli", "source_province_id": pid},
                ),
            )

        # Districts
        # Example district: { "district_id": 1, "name": "Kaski", "nepali_name": "कास्की", "province_id": 4 }
        for d in districts:
            did = int(d["district_id"])
            pid = int(d["province_id"])
            LocationNode.objects.update_or_create(
                id=_did(pid, did),
                defaults=dict(
                    type=LocationNode.Type.DISTRICT,
                    name_en=d["name"],
                    name_np=d.get("nepali_name", ""),
                    code=str(did),
                    parent_id=_pid(pid),
                    is_active=True,
                    meta={"source": "bibekoli", "source_district_id": did},
                ),
            )

        # Local Levels
        # Example local level:
        # { "municipality_id": 1, "name": "Pokhara", "nepali_name": "पोखरा", "district_id": 1, "local_level_type_id": 1 }
        # Note: dataset district_id is global; to construct parent, we must find its province_id first.
        district_to_province: Dict[int, int] = {int(d["district_id"]): int(d["province_id"]) for d in districts}

        for ll in local_levels:
            llid = int(ll["municipality_id"])
            did = int(ll["district_id"])
            pid = int(district_to_province[did])
            type_id = int(ll.get("local_level_type_id") or 0)
            type_name_en = type_map.get(type_id, ("Municipality", ""))[0]
            cat = _category_from_type(type_name_en)

            LocationNode.objects.update_or_create(
                id=_llid(pid, did, llid),
                defaults=dict(
                    type=LocationNode.Type.LOCAL_LEVEL,
                    name_en=ll["name"],
                    name_np=ll.get("nepali_name", ""),
                    code=str(llid),
                    parent_id=_did(pid, did),
                    is_active=True,
                    meta={
                        "source": "bibekoli",
                        "source_local_level_id": llid,
                        "local_level_category": cat,
                        "local_level_type_en": type_name_en,
                    },
                ),
            )

        if dry_run:
            raise RuntimeError("Dry-run requested; transaction rolled back.")

        self.stdout.write(self.style.SUCCESS("Imported Nepal provinces/districts/local-levels successfully."))