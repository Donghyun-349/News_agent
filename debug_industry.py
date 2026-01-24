import sqlite3
import json

# Check topics.db for Real Estate topics
conn = sqlite3.connect('data/topics.db')
cursor = conn.cursor()

# Get all topics
cursor.execute("SELECT id, category, topic_title FROM topics ORDER BY category, id")
all_topics = cursor.fetchall()

print("=" * 80)
print("ALL TOPICS BY CATEGORY")
print("=" * 80)

categories = {}
for t in all_topics:
    cat = t[1]
    if cat not in categories:
        categories[cat] = []
    categories[cat].append((t[0], t[2]))

for cat, topics in sorted(categories.items()):
    print(f"\n[{cat}] ({len(topics)} topics)")
    for tid, title in topics[:5]:  # Show first 5
        print(f"  {tid}: {title[:60]}")
    if len(topics) > 5:
        print(f"  ... and {len(topics) - 5} more")

# Check Real Estate specifically
print("\n" + "=" * 80)
print("REAL ESTATE TOPICS")
print("=" * 80)

cursor.execute("""
    SELECT id, category, topic_title 
    FROM topics 
    WHERE category LIKE '%Real%' OR category LIKE '%real%'
    ORDER BY id
""")

re_topics = cursor.fetchall()
if re_topics:
    for t in re_topics:
        print(f"ID={t[0]}, Category={t[1]}, Title={t[2]}")
else:
    print("NO Real Estate topics found!")

conn.close()
