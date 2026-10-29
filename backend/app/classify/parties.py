import re
from typing import Dict, List, Optional

from app.models.schemas import Party
from app.playbooks.loader import Playbook

_ORG = re.compile(
    r"\b((?:[A-Z][A-Za-z0-9&'\-]*\.?[ ]){0,5}[A-Z][A-Za-z0-9&'\-]*,?[ ]"
    r"(?:Inc\.?|LLC|L\.L\.C\.|Ltd\.?|Limited|Pvt\.?[ ]+Ltd\.?|Private[ ]+Limited|Corp\.?|Corporation|LLP|GmbH|S\.A\.|B\.V\.|Pte\.?[ ]+Ltd\.?|PLC|plc))(?![A-Za-z])"
)
_DEFINED = re.compile(
    r"([A-Z][A-Za-z0-9&.,'\- ]{2,120}?)\s*,?\s*\((?:the\s+|hereinafter\s+(?:referred\s+to\s+as\s+)?(?:the\s+)?)?[\"']([A-Z][A-Za-z ]{1,40})[\"']"
)
_DEAR = re.compile(r"\bDear\s+((?:Mr\.|Ms\.|Mrs\.|Dr\.)?\s?[A-Z][a-z]+(?:[ ][A-Z][a-z]+){0,3})\s*[,:]")
_COUNTRY_TAG = re.compile(r"\((US|USA|UK|EU|India|Europe|Asia|Singapore)\)")
_NOT_A_NAME = re.compile(
    r"^(you|your|we|our|us|i|he|she|they|it|his|her|their)\b|\b(will|shall|may|must|should|can|agrees?|report|is|are)\b", re.I)
_ROLE_WORDS = {"employee", "employer", "company", "executive", "consultant", "customer", "supplier", "client",
               "discloser", "recipient", "receiver", "vendor", "provider", "user", "candidate", "controller", "processor"}
_WELCOME = re.compile(r"\b(?:Welcome to|operated by|provided by)\s+([A-Z][A-Za-z0-9&\-]+(?:[ ][A-Z][A-Za-z0-9&\-]+){0,3})")
_STOP_LEADS = re.compile(r"^(this|the|by|and|between|that|which|such|all|any|one|each|for|from|of)\s+", re.I)
_DESCRIPTOR = re.compile(r",\s+(?:a|an|having|incorporated|registered|with|whose)\b.*$", re.I)
_NON_PARTY_ALIASES = {
    "agreement", "effective date", "purpose", "confidential information", "services", "service", "terms",
    "policy", "party", "parties", "platform", "software", "documentation", "territory", "term", "fees",
    "deliverables", "data", "personal data", "commencement date", "start date", "offer",
}


def _clean(name: str) -> str:
    name = re.sub(r"\s+", " ", name).strip(" ,.;:-\"'")
    name = re.split(r"\b(?:is|made|entered into)?\s*(?:by and between|between|by)\s+", name)[-1]
    while _STOP_LEADS.match(name):
        name = _STOP_LEADS.sub("", name, count=1)
    name = _DESCRIPTOR.sub("", name)
    return name.strip(" ,.;:-\"'")


def _looks_like_name(name: str) -> bool:
    if len(name) < 3 or len(name) > 80 or len(name.split()) > 8 or name.lower() in _NON_PARTY_ALIASES:
        return False
    if _NOT_A_NAME.search(name) or set(name.lower().split()) <= _ROLE_WORDS | {"and", "or", "other", "party", "the"}:
        return False
    if re.search(r"\b(service|services|platform|website|app|content|software)$", name, re.I):
        return False
    if re.search(r"\d{4}|\b(agreement|policy|terms|order form|schedule|exhibit|annexure|statement of work)\b", name, re.I):
        return False
    return name[0].isupper()


def _role_for(alias: str, playbook: Playbook) -> Optional[str]:
    a = alias.lower().strip()
    for p in playbook.perspectives:
        names = [x.lower() for x in p.aliases] + [p.label.lower(), p.id.replace("_", " ")]
        if any(a == n or a in n.split(" / ") or (len(n) > 3 and n in a) for n in names):
            return p.label
    return None


def extract_parties(text: str, playbook: Playbook) -> List[Party]:
    head = _COUNTRY_TAG.sub(r"\1", text[:6000])
    found: Dict[str, Party] = {}

    def add(name: str, role: Optional[str]) -> None:
        key = re.sub(r'\s*\("[^"]*"\)$', "", name).lower()
        if any(key in k or k in key for k in found):
            return
        found[key] = Party(name=name, role=role)

    for m in _DEFINED.finditer(head):
        alias = m.group(2).strip()
        if alias.lower() in _NON_PARTY_ALIASES:
            continue
        name = _clean(m.group(1))
        if not _looks_like_name(name) or name.lower() == alias.lower():
            continue
        role = _role_for(alias, playbook)
        add(name if alias.lower() in name.lower() else f'{name} ("{alias}")', role)

    for m in _ORG.finditer(head):
        name = _clean(m.group(1))
        if _looks_like_name(name):
            add(name, None)

    welcome = _WELCOME.search(head)
    if welcome:
        provider = next((p for p in playbook.perspectives if {"we", "us", "provider"} & {a.lower() for a in p.aliases}), None)
        add(_clean(welcome.group(1)), provider.label if provider else None)

    dear = _DEAR.search(head)
    if dear:
        person = _clean(dear.group(1))
        target = next((p for p in playbook.perspectives
                       if {"you", "candidate", "employee"} & {a.lower() for a in p.aliases}), None)
        if person:
            add(person, target.label if target else None)

    parties = list(found.values())
    unassigned = [p for p in parties if p.role is None]
    assigned_roles = {p.role for p in parties if p.role}
    if unassigned and len(assigned_roles) == 1:
        other = next((p.label for p in playbook.perspectives if p.label not in assigned_roles), None)
        unassigned[0].role = other
    return parties[:6]
