"""Conservative Germany-only location eligibility shared by all fetchers."""

import re
import unicodedata


def _fold(value: str) -> str:
    value = unicodedata.normalize("NFKD", (value or "").casefold().replace("ß", "ss"))
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


# Exact city-only evidence observed in dated exports plus common German hubs.
# Do not add ambiguous foreign cities without an explicit Germany qualifier.
_GERMAN_CITIES = frozenset(_fold(city) for city in """
Aachen
Aalen
Ahrensburg
Alsdorf
Amberg
Andernach
Aschaffenburg
Augsburg
Baunatal
Bad Hersfeld
Bad Kreuznach
Bayreuth
Bedburg
Beilngries
Bergheim
Bergkamen
Bielefeld
Bietigheim-Bissingen
Bonn
Braunschweig
Bremen
Bruehl
Bühl
Burgwedel
Celle
Chemnitz
Coburg
Cottbus
Damme
Darmstadt
Deggendorf
Dietzenbach
Dortmund
Dresden
Duisburg
Duesseldorf
Düsseldorf
Erlangen
Eschborn
Essen
Flensburg
Frankfurt
Frankfurt am Main
Frankfurt Oder
Freiburg
Freiburg im Breisgau
Frechen
Friedrichshafen
Fuerth
Fürth
Fulda
Garching
Gelsenkirchen
Gerolstein
Giessen
Gießen
Goettingen
Göttingen
Greifswald
Guetersloh
Gütersloh
Hagen
Halle
Hamburg
Hameln
Hanau
Hannover
Heidelberg
Heilbronn
Herford
Herrieden
Hildesheim
Ingolstadt
Jena
Kaiserslautern
Karlsruhe
Kassel
Kempten
Kiel
Koblenz
Koeln
Köln
Konstanz
Landshut
Langenfeld
Laupheim
Leipzig
Leverkusen
Luebeck
Lübeck
Luenen
Lünen
Magdeburg
Mainz
Manching
Mannheim
Marburg
Merzig
Moenchengladbach
Mönchengladbach
Moers
Moensheim
Mönsheim
Muelheim
Mülheim
Muenchen
München
Muenster
Münster
Neckarsulm
Neuss
Nuremberg
Nürnberg
Oberhaching
Oberkochen
Offenbach
Offenburg
Oldenburg
Olpe
Osnabrueck
Osnabrück
Ottobrunn
Paderborn
Passau
Pegnitz
Pforzheim
Pirmasens
Plattling
Poing
Potsdam
Rangendingen
Ratingen
Raubling
Regensburg
Remscheid
Reutlingen
Rosenheim
Rostock
Saarbruecken
Saarbrücken
Schramberg
Schweinfurt
Senftenberg
Siegen
Sindelfingen
Solingen
Steinau an der Straße
Stuttgart
Trier
Tuebingen
Tübingen
Ulm
Unterschleissheim
Unterschleißheim
Villingen-Schwenningen
Waldems
Weeze
Weimar
Wetzlar
Wiesbaden
Winterbach
Wolfsburg
Wolfertschwenden
Wuerzburg
Würzburg
Wuppertal
Zweibruecken
Zweibrücken
""".splitlines() if city.strip())

_GERMAN_CITIES |= frozenset(_fold(city) for city in (
    "Oberhaching bei München",
    "Ottobrunn bei München",
    "Munich",
    "Cologne",
    "Dusseldorf",
    "Pfullendorf",
    "Ortenburg",
    "Bamberg",
    "Brühl",
    "Grasbrunn",
    "Hattingen",
    "Hirschau",
    "Karlsdorf-Neuthard",
    "Kleinostheim",
    "Mülheim (Ruhr)",
    "Schwanau",
    "Stormarn",
))

_GERMAN_METRO_AREAS = frozenset(_fold(area) for area in (
    "Berlin Metropolitan Area",
    "Frankfurt Rhine-Main Metropolitan Area",
    "Greater Aschaffenburg Area",
    "Greater Dusseldorf Area",
    "Greater Düsseldorf Area",
    "Greater Hamburg Area",
    "Greater Koblenz Area",
    "Greater Munich Metropolitan Area",
    "Stuttgart Region",
))

_GERMAN_STATES = frozenset(_fold(state) for state in (
    "Baden-Württemberg", "Bavaria", "Bayern", "Brandenburg", "Berlin", "Bremen",
    "Hamburg", "Hesse", "Hessen", "Lower Saxony", "Niedersachsen",
    "Mecklenburg-West Pomerania", "Mecklenburg-Vorpommern", "North Rhine-Westphalia",
    "Nordrhein-Westfalen", "Rhineland-Palatinate", "Rheinland-Pfalz", "Saarland",
    "Saxony", "Sachsen", "Saxony-Anhalt", "Sachsen-Anhalt", "Schleswig-Holstein",
    "Thuringia", "Thüringen",
))

_COUNTRY_TOKENS = {"germany", "deutschland"}
_NEGATED_COUNTRY = re.compile(
    r"\b(?:no|not|outside|except|excluding|exclude|unavailable\s+in|"
    r"ineligible\s+in|not\s+(?:available|eligible|open|included|supported)\s+in)"
    r"(?:\s+[a-z0-9]+){0,3}\s+(?:germany|deutschland)\b|"
    r"\b(?:germany|deutschland)\b(?:\s+[a-z0-9]+){0,3}\s+"
    r"(?:excluded|unavailable|ineligible|unsupported|not\s+(?:available|eligible|open|included|supported))\b"
)
_LOCATION_SPLIT = re.compile(r"[;|/\n]+|\b(?:or|and)\b", re.IGNORECASE)
_POSTAL_PREFIX = re.compile(r"^\d{5}\s+")


def _has_positive_country_evidence(segment: str) -> bool:
    folded = _fold(segment)
    if _NEGATED_COUNTRY.search(folded):
        return False
    if _COUNTRY_TOKENS.intersection(folded.split()):
        return True
    # Source country codes are appended as uppercase, comma-separated values;
    # do not treat a lowercase prose token as country evidence.
    return any(part.strip() == "DE" for part in segment.split(","))

def _is_german_city_segment(segment: str) -> bool:
    raw = _POSTAL_PREFIX.sub("", segment.strip())
    folded = _fold(raw)
    if not folded:
        return False
    if folded in _GERMAN_CITIES or folded in _GERMAN_METRO_AREAS or folded in _GERMAN_STATES:
        return True

    # Some sources append a state to a city while omitting the country.
    parts = [_fold(part) for part in raw.split(",") if _fold(part)]
    if len(parts) > 1:
        if all(part in _GERMAN_CITIES for part in parts):
            return True
        if parts[-1] in _GERMAN_STATES and " ".join(parts[:-1]) in _GERMAN_CITIES:
            return True
    return False


def is_germany_location(location: str) -> bool:
    """Return true only for positive Germany, German-state, or German-city evidence.

    Empty/unknown and remote-region labels are not evidence. Explicit foreign
    locations are not accepted by substring matching; a separate explicit
    German option in a mixed location list still qualifies.
    """
    if not isinstance(location, str) or not location.strip():
        return False
    segments = [part.strip() for part in _LOCATION_SPLIT.split(location) if part.strip()]
    if any(_has_positive_country_evidence(part) for part in segments):
        return True
    return any(_is_german_city_segment(part) for part in segments)


_EU_REMOTE_REGION = re.compile(
    r"(?<![a-z0-9])(?:europe|european union|eu|eea|european economic area|"
    r"austria|belgium|bulgaria|croatia|cyprus|czechia|czech republic|denmark|"
    r"estonia|finland|france|greece|hungary|ireland|italy|latvia|lithuania|"
    r"luxembourg|malta|netherlands|poland|portugal|romania|slovakia|slovenia|"
    r"spain|sweden)(?![a-z0-9])"
)
_REMOTE_TOKEN = re.compile(r"(?<![a-z0-9])(?:remote|home office|homeoffice|anywhere in)(?![a-z0-9])")
_NON_EU_REMOTE = re.compile(
    r"(?<![a-z0-9])(?:global|worldwide|emea|amer|apac|americas|north america|"
    r"united states|usa|us only|uk only|canada)(?![a-z0-9])"
)


def is_eu_remote_location(location: str) -> bool:
    """True for explicit remote roles open in Europe/EU/an EU country.

    Requires both a remote marker and an EU region word. Global, EMEA, Americas
    and US-only labels are not evidence of EU eligibility.
    """
    if not isinstance(location, str) or not location.strip():
        return False
    for segment in _LOCATION_SPLIT.split(location):
        folded = _fold(segment)
        if (_REMOTE_TOKEN.search(folded) and _EU_REMOTE_REGION.search(folded)
                and not _NON_EU_REMOTE.search(folded) and not _NEGATED_COUNTRY.search(folded)):
            return True
    return False


def is_eligible_location(location: str) -> bool:
    """Germany (any city) or explicitly EU-remote."""
    return is_germany_location(location) or is_eu_remote_location(location)


def is_parttime_city(location: str, cities=None) -> bool:
    """Working-student/internship roles need Berlin/Potsdam or a Germany-remote role."""
    if not isinstance(location, str) or not location.strip():
        return False
    if cities is None:
        from config import PARTTIME_CITIES
        cities = PARTTIME_CITIES
    city_re = re.compile(r"(?<![a-z0-9])(?:" + "|".join(re.escape(_fold(c)) for c in cities) + r")(?![a-z0-9])")
    for segment in _LOCATION_SPLIT.split(location):
        folded = _fold(segment)
        if city_re.search(folded) and "new hampshire" not in folded:
            return True
        if _REMOTE_TOKEN.search(folded) and _has_positive_country_evidence(segment):
            return True
    return False


def is_role_location_eligible(role_type: str, location: str) -> bool:
    """Single location gate used by scraper, ATS fetchers and verification."""
    if not is_eligible_location(location):
        return False
    if role_type == "Working Student":
        return is_parttime_city(location)
    return True
