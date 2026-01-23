# generate_data.py
import random

filename = "Project_Phoenix_Specs.txt"

# 1. unique "Needle" hidden in the middle
secret_code = "ERR_CRITICAL_9982"
secret_budget = "$14,500,250.00"
secret_location = "Server Farm 42, Sector 7G"

content = [
    "# Project Phoenix: Enterprise Architecture Specification v4.2",
    "## 1. Executive Summary",
    "This document outlines the migration of legacy monoliths to a microservices architecture.",
    "It covers security, compliance, and infrastructure scaling strategies.",
    "\n"
]

# 2. Generate 50 pages of "Filler" Technical Jargon
components = ["Load Balancer", "Kafka Cluster", "Redis Cache", "Postgres Shard", "React Frontend"]
statuses = ["Operational", "Deprecated", "Refactoring", "Scaling"]

for i in range(1, 1000):
    section = f"## 2.{i} Component Infrastructure Log\n"
    section += f" - Component ID: COMP-{random.randint(1000,9999)}\n"
    section += f" - Type: {random.choice(components)}\n"
    section += f" - Status: {random.choice(statuses)}\n"
    section += " - Latency: 45ms\n"
    section += " - Throughput: 10k RPS\n\n"
    content.append(section)

# 3. Insert Specific Data Points (The "Needles") at random places
content.insert(500, f"\n## 5. Security Incident Log\nCRITICAL FAILURE: On Jan 12, system encountered error {secret_code} due to memory leak.\n")
content.insert(800, f"\n## 8. Financial Overview\nThe total allocated budget for Q4 infrastructure upgrade is {secret_budget}.\n")
content.insert(200, f"\n## 12. Physical Infrastructure\nThe primary backup data center is physically located at {secret_location}.\n")

# Write to file
with open(filename, "w") as f:
    f.writelines(content)

print(f"Generated {filename} with 1000+ sections.")