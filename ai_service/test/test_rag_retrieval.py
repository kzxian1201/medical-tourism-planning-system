# ai_service/test/test_rag_retrieval.py
import json
import asyncio
import os
import sys
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from ai_service.src.agentic.tools.medical_knowledge_base_tool import medical_knowledge_base

# Helper: Load JSON Data
def load_json_data(filename: str) -> List[Dict]:
    """Read the seed JSON file under src/data as Expected Data"""
    data_path = os.path.join(current_dir, '..', 'src', 'data', filename)
    try:
        with open(data_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"⚠️ Warning: {filename} not found at {data_path}.")
        return []

def get_test_cases(filename: str, category: str, id_field: str = "id") -> List[Dict]:
    """Generate test cases for entity knowledge base retrieval"""
    data = load_json_data(filename)
    cases = []
    for item in data[:3]:
        expected_id = item.get(id_field)
        name = item.get("name") or expected_id
        if expected_id and name:
            cases.append({
                "category": category,
                "query": name,
                "expected_id": expected_id,
                "desc": f"Search [{category}] by name: {name}"
            })
    return cases

# Helper: Evaluate Single Retrieval Case
async def _evaluate_single_case(test: dict) -> bool:
    """Evaluate the retrieval case and return if it passed"""
    try:
        response = await medical_knowledge_base.ainvoke({
            "category": test['category'],
            "query": test['query']
        })
        
        retrieved_ids = []
        for item in response.results:
            item_id = item.get('_entity_id')
            if item_id:
                retrieved_ids.append(item_id)
                if item_id == test['expected_id']:
                    print(f"   ✅ PASS (Found {test['expected_id']})")
                    return True
        
        print(f"   ❌ FAIL (Expected: {test['expected_id']})")
        print(f"      -> Retrieved IDs: {retrieved_ids}")
        return False
            
    except Exception as e:
        print(f"   ⚠️ ERROR: {e}")
        return False

# Unit Test Runner
async def run_retrieval_tests():
    print("\n" + "="*50)
    print("🔬 UNIT TEST: ENTITY KNOWLEDGE BASE RETRIEVAL")
    print("="*50 + "\n")

    all_tests = []
    all_tests.extend(get_test_cases('hospitals.json', 'hospital', 'id'))
    all_tests.extend(get_test_cases('doctors.json', 'doctor', 'id'))
    all_tests.extend(get_test_cases('treatments.json', 'treatment', 'id'))
    
    total = len(all_tests)
    if total == 0:
        print("❌ No test cases generated. Check JSON file paths.")
        return

    print(f"📋 Total Retrieval Cases: {total}\n")

    passed = 0
    for i, test in enumerate(all_tests):
        print(f"🔹 [{i+1}/{total}] {test['desc']}")
        
        if await _evaluate_single_case(test):
            passed += 1
            
        print("-" * 40)

    score = (passed / total) * 100
    print(f"\n🎯 FINAL SCORE: {passed}/{total} ({score:.1f}%)")
    if score == 100:
        print("🏆 Excellent! The SQLite Entity Store retrieval is perfectly accurate.")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_retrieval_tests())

# run this: python -m ai_service.test.test_rag_retrieval