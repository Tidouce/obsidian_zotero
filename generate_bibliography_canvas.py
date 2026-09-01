from pathlib import Path
import json
import re
import math
from collections import Counter


# ============================================================
# CONFIGURATION
# ============================================================

# Le script doit être placé dans le dossier "Scripts" du vault.
VAULT = Path(__file__).resolve().parent.parent

NOTES_DIR = VAULT / "Notes_zotero"
OUTPUT = VAULT / "Bibliography.canvas"


# ------------------------------------------------------------
# TAILLE DES NŒUDS
# ------------------------------------------------------------

# Articles
ARTICLE_WIDTH = 260
ARTICLE_HEIGHT = 80

# Tags
# La taille réelle sera ensuite calculée automatiquement
# en fonction du nombre d'articles associés.
TAG_MIN_WIDTH = 120
TAG_MAX_WIDTH = 280

TAG_MIN_HEIGHT = 50
TAG_MAX_HEIGHT = 100


# ------------------------------------------------------------
# DISPOSITION
# ------------------------------------------------------------

# Taille générale de la carte.
# Augmente ces valeurs si ta bibliographie est très importante.
CANVAS_WIDTH = 5000
CANVAS_HEIGHT = 4000

# Nombre d'itérations de la simulation de forces.
# Plus élevé = disposition plus stable, mais calcul plus long.
ITERATIONS = 700

# ------------------------------------------------------------
# FORCES
# ------------------------------------------------------------

# Répulsion générale entre les nœuds.
REPULSION = 180000

# Attraction des articles vers leurs tags.
ARTICLE_TAG_ATTRACTION = 0.018

# Attraction des tags vers le centre.
# Les tags importants ont une attraction plus forte.
TAG_CENTER_ATTRACTION = 0.012

# Attraction supplémentaire des articles vers le centre.
# Faible : les articles restent principalement organisés
# par leurs tags.
ARTICLE_CENTER_ATTRACTION = 0.0008

# Longueur naturelle des connexions article <-> tag.
EDGE_LENGTH = 420

# Force utilisée pour rapprocher les articles et les tags
# lorsqu'ils sont trop éloignés.
SPRING_FORCE = 0.012

# Marge supplémentaire entre les nœuds.
NODE_MARGIN = 80

# Vitesse maximale d'un déplacement pendant une itération.
MAX_STEP = 45

# Refroidissement progressif de la simulation.
COOLING = 0.992


# ============================================================
# LECTURE DU FRONTMATTER
# ============================================================

def extract_frontmatter(text):
    """
    Extrait le YAML situé entre les deux premiers ---.

    Ce parser reste volontairement simple afin de ne pas
    dépendre d'un module YAML externe.
    """

    if not text.startswith("---"):
        return {}

    match = re.match(
        r"^---\s*\n(.*?)\n---\s*",
        text,
        re.DOTALL
    )

    if not match:
        return {}

    yaml_text = match.group(1)
    data = {}

    current_key = None

    for line in yaml_text.splitlines():

        # ----------------------------------------------------
        # key: value
        # ----------------------------------------------------

        match = re.match(
            r"^([A-Za-z0-9 _()\-]+):\s*(.*)$",
            line
        )

        if match:

            key = match.group(1).strip()
            value = match.group(2).strip()

            current_key = key

            # Liste vide
            if not value:
                data[key] = []

            # Liste inline :
            # [tag1, tag2, tag3]
            elif value.startswith("[") and value.endswith("]"):

                inside = value[1:-1].strip()

                if inside:

                    items = [
                        x.strip().strip('"').strip("'")
                        for x in inside.split(",")
                    ]

                    data[key] = items

                else:
                    data[key] = []

            else:

                data[key] = (
                    value
                    .strip('"')
                    .strip("'")
                )

            continue

        # ----------------------------------------------------
        # Liste YAML :
        #
        # tags:
        #   - task
        #   - water
        # ----------------------------------------------------

        elif (
            current_key
            and re.match(r"^\s+-\s+", line)
        ):

            value = re.sub(
                r"^\s+-\s+",
                "",
                line
            )

            value = (
                value
                .strip()
                .strip('"')
                .strip("'")
            )

            if not isinstance(
                data.get(current_key),
                list
            ):
                data[current_key] = []

            data[current_key].append(value)

    return data


# ============================================================
# NORMALISATION DES TAGS
# ============================================================

def get_tags(frontmatter):
    """
    Transforme les différentes formes possibles de tags
    en une liste propre et sans doublons.
    """

    tags = frontmatter.get("tags", [])

    if isinstance(tags, str):

        # Cas :
        # tags: task, water

        if "," in tags:
            tags = [
                x.strip()
                for x in tags.split(",")
            ]

        else:
            tags = [tags]

    if not isinstance(tags, list):
        return []

    cleaned = []

    for tag in tags:

        if not tag:
            continue

        tag = str(tag).strip()

        # Obsidian accepte aussi #tag
        tag = tag.lstrip("#").strip()

        if tag and tag not in cleaned:
            cleaned.append(tag)

    return cleaned


# ============================================================
# LECTURE DES ARTICLES
# ============================================================

articles = []

for md_file in sorted(NOTES_DIR.glob("*.md")):

    try:

        text = md_file.read_text(
            encoding="utf-8"
        )

    except UnicodeDecodeError:

        print(
            f"Impossible de lire : {md_file}"
        )

        continue

    frontmatter = extract_frontmatter(text)

    tags = get_tags(frontmatter)

    relative_path = (
        md_file
        .relative_to(VAULT)
        .as_posix()
    )

    articles.append({
        "name": md_file.stem,
        "path": relative_path,
        "tags": tags
    })


# ============================================================
# STATISTIQUES DES TAGS
# ============================================================

tag_counts = Counter(
    tag
    for article in articles
    for tag in article["tags"]
)

all_tags = sorted(
    tag_counts.keys()
)


# ============================================================
# NORMALISATION D'UNE VALEUR
# ============================================================

def normalize(value, minimum, maximum):
    """
    Ramène value dans l'intervalle 0-1.
    """

    if maximum == minimum:
        return 1.0

    return (
        (value - minimum)
        / (maximum - minimum)
    )


# ============================================================
# IMPORTANCE DES TAGS
# ============================================================

if tag_counts:

    min_count = min(
        tag_counts.values()
    )

    max_count = max(
        tag_counts.values()
    )

else:

    min_count = 0
    max_count = 0


tag_importance = {}

for tag in all_tags:

    count = tag_counts[tag]

    # --------------------------------------------------------
    # Echelle logarithmique
    #
    # Elle évite qu'un tag utilisé 100 fois écrase
    # complètement un tag utilisé 20 fois.
    # --------------------------------------------------------

    log_count = math.log1p(count)
    log_min = math.log1p(min_count)
    log_max = math.log1p(max_count)

    if log_max == log_min:
        importance = 1.0
    else:
        importance = (
            (log_count - log_min)
            / (log_max - log_min)
        )

    tag_importance[tag] = importance


# ============================================================
# TAILLE DES TAGS
# ============================================================

def tag_dimensions(tag):

    importance = tag_importance[tag]

    # Interpolation douce de la taille.
    width = (
        TAG_MIN_WIDTH
        + (
            TAG_MAX_WIDTH
            - TAG_MIN_WIDTH
        ) * importance
    )

    height = (
        TAG_MIN_HEIGHT
        + (
            TAG_MAX_HEIGHT
            - TAG_MIN_HEIGHT
        ) * importance
    )

    return (
        round(width),
        round(height)
    )


# ============================================================
# COULEUR DES TAGS
# ============================================================

def tag_color(tag):
    """
    Les tags importants reçoivent une couleur plus forte.

    Les couleurs Canvas Obsidian utilisent les valeurs
    textuelles 1 à 6.
    """

    importance = tag_importance[tag]

    if importance >= 0.85:
        return "1"

    if importance >= 0.65:
        return "2"

    if importance >= 0.45:
        return "3"

    if importance >= 0.25:
        return "4"

    if importance >= 0.10:
        return "5"

    return "6"


# ============================================================
# STRUCTURE DES NŒUDS
# ============================================================

nodes = []
edges = []

tag_nodes = {}
article_nodes = {}

positions = {}


# ============================================================
# INITIALISATION DES POSITIONS
# ============================================================

# ------------------------------------------------------------
# TAGS
#
# On utilise une spirale plutôt qu'un cercle.
# Les tags importants commencent près du centre.
# ------------------------------------------------------------

sorted_tags = sorted(
    all_tags,
    key=lambda tag: (
        -tag_counts[tag],
        tag
    )
)

golden_angle = math.pi * (
    3 - math.sqrt(5)
)

for i, tag in enumerate(sorted_tags):

    importance = tag_importance[tag]

    # Distance initiale au centre.
    #
    # Important :
    # plus le tag est important,
    # plus il commence près du centre.
    radius = (
        180
        + (1.0 - importance) * 1000
    )

    angle = (
        i * golden_angle
    )

    x = radius * math.cos(angle)
    y = radius * math.sin(angle)

    positions[tag] = [
        x,
        y
    ]


# ------------------------------------------------------------
# ARTICLES
#
# Les articles commencent eux aussi dans une spirale,
# mais plus loin du centre.
# ------------------------------------------------------------

article_count = len(articles)

for i, article in enumerate(articles):

    angle = (
        i * golden_angle
        + 1.3
    )

    # Distribution initiale suffisamment large.
    radius = (
        700
        + math.sqrt(
            max(article_count, 1)
        ) * 120
    )

    # Variation déterministe supplémentaire.
    radius += (
        (i % 7) * 90
    )

    x = radius * math.cos(angle)
    y = radius * math.sin(angle)

    positions[
        article["path"]
    ] = [
        x,
        y
    ]


# ============================================================
# DIMENSIONS DES NŒUDS
# ============================================================

node_dimensions = {}

for tag in all_tags:

    node_dimensions[tag] = tag_dimensions(tag)


for article in articles:

    node_dimensions[
        article["path"]
    ] = (
        ARTICLE_WIDTH,
        ARTICLE_HEIGHT
    )


# ============================================================
# FONCTION DE DISTANCE
# ============================================================

def distance(x1, y1, x2, y2):

    dx = x2 - x1
    dy = y2 - y1

    distance_value = math.sqrt(
        dx * dx
        + dy * dy
    )

    # Évite une division par zéro.
    return max(distance_value, 1.0)


# ============================================================
# SIMULATION DE FORCES
# ============================================================

print()
print("Calcul de la disposition...")
print(
    f"{len(articles)} articles / "
    f"{len(all_tags)} tags"
)


# Liste de tous les identifiants.
all_ids = (
    all_tags
    + [
        article["path"]
        for article in articles
    ]
)


# ------------------------------------------------------------
# Simulation
# ------------------------------------------------------------

for iteration in range(ITERATIONS):

    forces = {
        node_id: [0.0, 0.0]
        for node_id in all_ids
    }

    # ========================================================
    # 1. REPULSION ENTRE TOUS LES NŒUDS
    # ========================================================

    for i in range(len(all_ids)):

        node_a = all_ids[i]

        xa, ya = positions[node_a]

        wa, ha = node_dimensions[node_a]

        for j in range(i + 1, len(all_ids)):

            node_b = all_ids[j]

            xb, yb = positions[node_b]

            wb, hb = node_dimensions[node_b]

            dx = xb - xa
            dy = yb - ya

            dist = math.sqrt(
                dx * dx
                + dy * dy
            )

            if dist < 1:
                dist = 1.0
                dx = 1.0
                dy = 0.0

            # Taille effective des nœuds.
            min_distance = (
                max(wa, wb) / 2
                + max(ha, hb) / 2
                + NODE_MARGIN
            )

            # Répulsion générale.
            force = (
                REPULSION
                / (dist * dist)
            )

            # Si les nœuds se chevauchent,
            # on augmente fortement la répulsion.
            if dist < min_distance:

                overlap_factor = (
                    min_distance / dist
                )

                force *= (
                    1
                    + overlap_factor * 5
                )

            fx = (
                force
                * dx
                / dist
            )

            fy = (
                force
                * dy
                / dist
            )

            forces[node_a][0] -= fx
            forces[node_a][1] -= fy

            forces[node_b][0] += fx
            forces[node_b][1] += fy


    # ========================================================
    # 2. ATTRACTION DES TAGS VERS LE CENTRE
    # ========================================================

    for tag in all_tags:

        x, y = positions[tag]

        importance = tag_importance[tag]

        # Les tags importants ont une attraction
        # plus forte vers le centre.
        attraction = (
            TAG_CENTER_ATTRACTION
            * (
                0.25
                + importance
            )
        )

        forces[tag][0] -= (
            x * attraction
        )

        forces[tag][1] -= (
            y * attraction
        )


    # ========================================================
    # 3. ATTRACTION DES ARTICLES VERS LEURS TAGS
    # ========================================================

    for article in articles:

        article_id = article["path"]

        ax, ay = positions[article_id]

        tags = article["tags"]

        if not tags:
            continue

        for tag in tags:

            if tag not in positions:
                continue

            tx, ty = positions[tag]

            dx = tx - ax
            dy = ty - ay

            dist = math.sqrt(
                dx * dx
                + dy * dy
            )

            if dist < 1:
                dist = 1.0

            # Ressort :
            # l'article cherche à se rapprocher
            # de son tag, mais pas à se coller à lui.
            displacement = (
                dist
                - EDGE_LENGTH
            )

            force = (
                SPRING_FORCE
                * displacement
            )

            fx = (
                force
                * dx
                / dist
            )

            fy = (
                force
                * dy
                / dist
            )

            forces[article_id][0] += fx
            forces[article_id][1] += fy

            forces[tag][0] -= fx
            forces[tag][1] -= fy


    # ========================================================
    # 4. ARTICLES LÉGÈREMENT ATTIRÉS VERS LE CENTRE
    # ========================================================

    for article in articles:

        article_id = article["path"]

        x, y = positions[article_id]

        forces[article_id][0] -= (
            x * ARTICLE_CENTER_ATTRACTION
        )

        forces[article_id][1] -= (
            y * ARTICLE_CENTER_ATTRACTION
        )


    # ========================================================
    # 5. APPLICATION DES FORCES
    # ========================================================

    temperature = (
        MAX_STEP
        * (COOLING ** iteration)
    )

    for node_id in all_ids:

        fx, fy = forces[node_id]

        magnitude = math.sqrt(
            fx * fx
            + fy * fy
        )

        if magnitude < 0.0001:
            continue

        # Limitation du déplacement.
        scale = min(
            1.0,
            temperature / magnitude
        )

        positions[node_id][0] += (
            fx * scale
        )

        positions[node_id][1] += (
            fy * scale
        )


# ============================================================
# RECENTRAGE FINAL
# ============================================================

if positions:

    average_x = sum(
        pos[0]
        for pos in positions.values()
    ) / len(positions)

    average_y = sum(
        pos[1]
        for pos in positions.values()
    ) / len(positions)

    for node_id in positions:

        positions[node_id][0] -= average_x
        positions[node_id][1] -= average_y


# ============================================================
# CONSTRUCTION DES NŒUDS TAGS
# ============================================================

for i, tag in enumerate(sorted_tags):

    x, y = positions[tag]

    width, height = node_dimensions[tag]

    count = tag_counts[tag]

    tag_id = f"tag-{i}"

    tag_nodes[tag] = tag_id

    nodes.append({
        "id": tag_id,
        "type": "text",
        "text": (
            f"# {tag}\n"
            f"{count} article"
            + (
                "s"
                if count > 1
                else ""
            )
        ),
        "x": round(
            x - width / 2
        ),
        "y": round(
            y - height / 2
        ),
        "width": width,
        "height": height,
        "color": tag_color(tag)
    })


# ============================================================
# CONSTRUCTION DES NŒUDS ARTICLES
# ============================================================

for i, article in enumerate(articles):

    article_id = f"article-{i}"

    article_nodes[
        article["path"]
    ] = article_id

    x, y = positions[
        article["path"]
    ]

    nodes.append({
        "id": article_id,
        "type": "file",
        "file": article["path"],
        "x": round(
            x - ARTICLE_WIDTH / 2
        ),
        "y": round(
            y - ARTICLE_HEIGHT / 2
        ),
        "width": ARTICLE_WIDTH,
        "height": ARTICLE_HEIGHT
    })


# ============================================================
# CONNEXIONS ARTICLES → TAGS
# ============================================================

edge_counter = 0

for article in articles:

    article_id = article_nodes[
        article["path"]
    ]

    for tag in article["tags"]:

        if tag not in tag_nodes:
            continue

        edges.append({
            "id": f"edge-{edge_counter}",
            "fromNode": article_id,
            "toNode": tag_nodes[tag]
        })

        edge_counter += 1


# ============================================================
# CALCUL DE LA TAILLE DE LA CARTE
# ============================================================

if positions:

    min_x = min(
        positions[node_id][0]
        - node_dimensions[node_id][0] / 2
        for node_id in positions
    )

    max_x = max(
        positions[node_id][0]
        + node_dimensions[node_id][0] / 2
        for node_id in positions
    )

    min_y = min(
        positions[node_id][1]
        - node_dimensions[node_id][1] / 2
        for node_id in positions
    )

    max_y = max(
        positions[node_id][1]
        + node_dimensions[node_id][1] / 2
        for node_id in positions
    )

    content_width = max_x - min_x
    content_height = max_y - min_y

else:

    content_width = CANVAS_WIDTH
    content_height = CANVAS_HEIGHT


# ============================================================
# LIMITATION DE LA TAILLE
# ============================================================

# On évite une carte excessivement grande.
#
# Le contenu est simplement recentré ; les coordonnées
# restent volontairement libres afin de ne pas écraser
# les distances calculées par la simulation.

if content_width > CANVAS_WIDTH:

    scale_x = (
        CANVAS_WIDTH
        / content_width
    )

else:

    scale_x = 1.0


if content_height > CANVAS_HEIGHT:

    scale_y = (
        CANVAS_HEIGHT
        / content_height
    )

else:

    scale_y = 1.0


scale = min(
    scale_x,
    scale_y
)


# ============================================================
# APPLICATION DE L'ÉCHELLE FINALE
# ============================================================

if scale < 1.0:

    for node_id in positions:

        positions[node_id][0] *= scale
        positions[node_id][1] *= scale

    # Recalcule les positions dans les nœuds déjà créés.
    # Les coordonnées seront reconstruites ci-dessous.


# ============================================================
# RECONSTRUCTION DES NŒUDS AVEC POSITIONS FINALES
# ============================================================

nodes = []


# ------------------------------------------------------------
# TAGS
# ------------------------------------------------------------

for i, tag in enumerate(sorted_tags):

    x, y = positions[tag]

    width, height = node_dimensions[tag]

    tag_id = tag_nodes[tag]

    count = tag_counts[tag]

    nodes.append({
        "id": tag_id,
        "type": "text",
        "text": (
            f"# {tag}\n"
            f"{count} article"
            + (
                "s"
                if count > 1
                else ""
            )
        ),
        "x": round(
            x - width / 2
        ),
        "y": round(
            y - height / 2
        ),
        "width": width,
        "height": height,
        "color": tag_color(tag)
    })


# ------------------------------------------------------------
# ARTICLES
# ------------------------------------------------------------

for i, article in enumerate(articles):

    article_id = article_nodes[
        article["path"]
    ]

    x, y = positions[
        article["path"]
    ]

    nodes.append({
        "id": article_id,
        "type": "file",
        "file": article["path"],
        "x": round(
            x - ARTICLE_WIDTH / 2
        ),
        "y": round(
            y - ARTICLE_HEIGHT / 2
        ),
        "width": ARTICLE_WIDTH,
        "height": ARTICLE_HEIGHT
    })


# ============================================================
# ÉCRITURE DU FICHIER CANVAS
# ============================================================

canvas = {
    "nodes": nodes,
    "edges": edges
}

OUTPUT.write_text(
    json.dumps(
        canvas,
        indent=2,
        ensure_ascii=False
    ),
    encoding="utf-8"
)


# ============================================================
# RAPPORT
# ============================================================

print()
print("========================================")
print("Bibliography Canvas généré")
print("========================================")

print(
    f"Articles : {len(articles)}"
)

print(
    f"Tags     : {len(all_tags)}"
)

print(
    f"Liens    : {len(edges)}"
)

print()

if tag_counts:

    print("Importance des tags :")
    print()

    for tag in sorted_tags:

        count = tag_counts[tag]
        importance = tag_importance[tag]

        print(
            f"  {tag:<35} "
            f"{count:>4} articles  "
            f"importance = {importance:.2f}"
        )

    print()

print(
    f"Fichier : {OUTPUT}"
)

print()
