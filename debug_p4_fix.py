import json
import logging
from run_p4 import call_llm_batch_no_json_mode

# Mock OpenAI client
class MockChoice:
    def __init__(self, content):
        self.message = type('obj', (object,), {'content': content})

class MockResponse:
    def __init__(self, content):
        self.choices = [MockChoice(content)]

class MockClient:
    def __init__(self, content_to_return):
        self.content = content_to_return
        self.chat = type('obj', (object,), {'completions': type('obj', (object,), {'create': self.create})})()

    def create(self, **kwargs):
        return MockResponse(self.content)

# Setup Logger
logging.basicConfig(level=logging.INFO)

def test_robust_parsing():
    print("Testing Robust Parsing...")
    
    # Case 1: Extra data at the end (The error user saw)
    bad_content = '[[1, 1, "K_mac", "Reason"]] \n Some extra text here'
    client = MockClient(bad_content)
    res = call_llm_batch_no_json_mode(client, [{"id":1, "title":"test"}])
    print(f"Case 1 Result: {res}")
    assert len(res) == 1
    assert res[0]['category'] == 'K_mac'
    
    # Case 2: Markdown blocks
    markdown_content = '```json\n[[2, 1, "G_mac", "Reason"]]\n```'
    client = MockClient(markdown_content)
    res = call_llm_batch_no_json_mode(client, [{"id":2, "title":"test"}])
    print(f"Case 2 Result: {res}")
    assert len(res) == 1
    assert res[0]['category'] == 'G_mac'

    print("✅ Logic Verified!")

if __name__ == "__main__":
    test_robust_parsing()
