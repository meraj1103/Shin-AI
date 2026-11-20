import sys
sys.path.insert(0, 'Shin')
sys.path.insert(0, 'Shin/core')

# Test Vector Memory
from core.vector_memory import VectorMemoryManager, MemoryType, MemoryImportance

vm = VectorMemoryManager()

# Add test memories
id1 = vm.remember("MJ loves coding in Python and uses VS Code", MemoryType.SEMANTIC, MemoryImportance.HIGH, ["preference", "coding"])
print("Added memory 1:", id1)

id2 = vm.remember("MJ's sister is named Priya", MemoryType.SEMANTIC, MemoryImportance.HIGH, ["family"])
print("Added memory 2:", id2)

id3 = vm.remember("Had a great coding session yesterday building a React app", MemoryType.EPISODIC, MemoryImportance.MEDIUM, ["coding", "session"])
print("Added memory 3:", id3)

# Test recall
print()
print("Recall: What does MJ like to code in?")
results = vm.recall("What does MJ like to code in?")
for r in results:
    print("  [{:.2f}] {}".format(r['score'], r['content']))

print()
print("Recall: family")
results = vm.recall("family")
for r in results:
    print("  [{:.2f}] {}".format(r['score'], r['content']))

print()
print("Context for prompt:")
print(vm.get_context_for_prompt("coding preferences"))

print()
print("Stats:")
import json
print(json.dumps(vm.get_stats(), indent=2, default=str))