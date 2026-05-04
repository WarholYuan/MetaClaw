import sys
import os
import re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

SKILL_PATH = os.path.join(os.path.dirname(__file__), '..', 'skills', 'lark-cli', 'SKILL.md')


def test_skill_file_exists():
    assert os.path.exists(SKILL_PATH), f"SKILL.md not found at {SKILL_PATH}"


def test_skill_has_frontmatter():
    with open(SKILL_PATH, 'r', encoding='utf-8') as f:
        content = f.read()
    assert content.startswith('---'), "Missing YAML frontmatter opening"
    assert '---' in content[3:], "Missing YAML frontmatter closing"


def test_skill_frontmatter_contains_name_and_description():
    with open(SKILL_PATH, 'r', encoding='utf-8') as f:
        content = f.read()
    match = re.search(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    assert match, "Could not parse frontmatter"
    frontmatter = match.group(1)
    assert 'name:' in frontmatter, "Missing name field"
    assert 'description:' in frontmatter, "Missing description field"
    assert 'lark-cli' in frontmatter or 'lark' in frontmatter.lower(), "Missing lark reference"


def test_skill_contains_auth_path_and_examples():
    with open(SKILL_PATH, 'r', encoding='utf-8') as f:
        content = f.read()
    lower = content.lower()
    assert '.lark-cli' in content or 'auth' in lower, "Missing auth/config reference"
    assert 'send' in lower or '消息' in content, "Missing send message example"
    assert 'calendar' in lower or '日程' in content or '日历' in content, "Missing calendar reference"
    assert 'search' in lower or '用户' in content, "Missing user search reference"
