
from pathlib import Path
import json
import re
import math

# ============================================================
# CONFIGURATION
# ============================================================

# Le script doit être placé dans le dossier "Scripts" du vault.
VAULT = Path(__file__).resolve().parent.parent

NOTES_DIR = VAULT / "Notes_zotero"
OUTPUT = VAULT / "Bibliography.canvas"

# Taille des nœuds

ARTICLE_WIDTH = 260
ARTICLE_HEIGHT = 80
TAG_WIDTH = 180
TAG_HEIGHT = 60

# Distance entre les cercles
TAG_RADIUS = 500
ARTICLE_RADIUS = 1100


# ============================================================
# LECTURE DU FRONTMATTER
# ============================================================

def extract_frontmatter(text):
    """
    Extrait le YAML situé entre les deux premiers ---.
    On évite ici de dépendre d'un module YAML externe.
    """

    if not text.startswith("---"):
        return {}

    match = re.match(r"^---\s*\n(.*?)\n---\s*", text, re.DOTALL)

    if not match:
        return {}

    yaml_text = match.group(1)
    data = {}

    current_key = None

    for line in yaml_text.splitlines():
        # key: value
        match = re.match(r"^([A-Za-z0-9 _()\-]+):\s*(.*)$", line)

        if match:
            key = match.group(1).strip()
            value = match.group(2).strip()

            current_key = key

            if not value:
                data[key] = []
            elif value.startswith("[") and value.endswith("]"):
                # Liste inline : [tag1, tag2]
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
                data[key] = value.strip('"').strip("'")

        # Liste YAML :
        # tags:
        #   - task
        #   - water
        elif current_key and re.match(r"^\s+-\s+", line):
            value = re.sub(r"^\s+-\s+", "", line)
            value = value.strip().strip('"').strip("'")

            if not isinstance(data.get(current_key), list):
                data[current_key] = []

            data[current_key].append(value)

    return data


# ============================================================
# NORMALISATION DES TAGS
# ============================================================

def get_tags(frontmatter):
    """
    Transforme différentes formes possibles de tags
    en une liste propre.
    """

    tags = frontmatter.get("tags", [])

    if isinstance(tags, str):
        # Cas : "task, water"
        if "," in tags:
            tags = [x.strip() for x in tags.split(",")]
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
        text = md_file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        print(f"Impossible de lire : {md_file}")
        continue

    frontmatter = extract_frontmatter(text)
    tags = get_tags(frontmatter)

    relative_path = md_file.relative_to(VAULT).as_posix()

    articles.append({
        "name": md_file.stem,
        "path": relative_path,
        "tags": tags
    })


# ============================================================
# LISTE DES TAGS
# ============================================================

all_tags = sorted({
    tag
    for article in articles
    for tag in article["tags"]
})


# ============================================================
# CONSTRUCTION DU CANVAS
# ============================================================

nodes = []
edges = []

# ------------------------------------------------------------
# TAGS
# ------------------------------------------------------------

tag_count = len(all_tags)

if tag_count == 0:
    print("Aucun tag trouvé.")
else:

    center_x = 0
    center_y = 0

    for i, tag in enumerate(all_tags):

        angle = (
            2 * math.pi * i / tag_count
            - math.pi / 2
        )

        x = center_x + TAG_RADIUS * math.cos(angle)
        y = center_y + TAG_RADIUS * math.sin(angle)

        tag_id = f"tag-{i}"

        nodes.append({
            "id": tag_id,
            "type": "text",
            "text": f"# {tag}",
            "x": round(x),
            "y": round(y),
            "width": TAG_WIDTH,
            "height": TAG_HEIGHT,
            "color": "5"
        })


# ------------------------------------------------------------
# ARTICLES
# ------------------------------------------------------------

article_nodes = {}

article_count = len(articles)

for i, article in enumerate(articles):

    angle = (
        2 * math.pi * i / max(article_count, 1)
        - math.pi / 2
    )

    x = ARTICLE_RADIUS * math.cos(angle)
    y = ARTICLE_RADIUS * math.sin(angle)

    article_id = f"article-{i}"

    nodes.append({
        "id": article_id,
        "type": "file",
        "file": article["path"],
        "x": round(x),
        "y": round(y),
        "width": ARTICLE_WIDTH,
        "height": ARTICLE_HEIGHT
    })

    article_nodes[article["path"]] = article_id


# ------------------------------------------------------------
# CONNEXIONS ARTICLES → TAGS
# ------------------------------------------------------------

tag_nodes = {
    node["text"][2:]: node["id"]
    for node in nodes
    if node["id"].startswith("tag-")
}

edge_counter = 0

for article in articles:

    article_id = article_nodes[article["path"]]

    for tag in article["tags"]:

        if tag not in tag_nodes:
            continue

        edges.append({
            "id": f"edge-{edge_counter}",
            "fromNode": article_id,
            "toNode": tag_nodes[tag],
            "fromSide": "left",
            "toSide": "right"
        })

        edge_counter += 1


# ============================================================
# ÉCRITURE DU FICHIER CANVAS
# ============================================================

canvas = {
    "nodes": nodes,
    "edges": edges
}

OUTPUT.write_text(
    json.dumps(canvas, indent=2, ensure_ascii=False),
    encoding="utf-8"
)


# ============================================================
# RAPPORT
# ============================================================

print()
print("========================================")
print("Bibliography Canvas généré")
print("========================================")
print(f"Articles : {len(articles)}")
print(f"Tags     : {len(all_tags)}")
print(f"Liens    : {len(edges)}")
print()
print(f"Fichier : {OUTPUT}")
print()

