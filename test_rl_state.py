import os
import sys
import logging
from unittest.mock import MagicMock

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add paths
sys.path.append(os.getcwd())

try:
    from studentProfileDetails.agents.mainAgent import diagnosis_chat
    from studentProfileDetails.agents.rl_optimizer import RLOptimizer
    
    # Mock student_agent
    mock_agent = MagicMock()
    mock_agent.ask.return_value = {
        "response": "This is a test response",
        "quality_scores": {"rag_relevance": 80, "answer_completeness": 90, "hallucination_risk": 5}
    }
    
    # Mock profile
    student_profile = {
        "level": "basic",
        "tone": "friendly",
        "learning_style": "step-by-step",
        "response_length": "long",
        "include_example": True,
        "confusion_counter": {},
        "common_mistakes": []
    }
    
    print("Testing diagnosis_chat with new RL state structure...")
    result = diagnosis_chat(
        student_agent=mock_agent,
        query="What is a chemical reaction?",
        class_name="12",
        subject="Chemistry-1",
        student_profile=student_profile,
        context=[]
    )
    
    print("\nRL Metadata found:")
    print(result.get("rl_metadata"))
    
    print("\nTesting reward calculation and define_state direct call...")
    optimizer = RLOptimizer()
    state = optimizer.define_state(
        query="What is a chemical reaction?",
        context_chunks=["some data"],
        student_profile=student_profile,
        rewritten_query="rewritten query...",
        previous_responses=["previous answer"],
        previous_actions=["rewrite_query"],
        previous_rewards=[0.5]
    )
    print("State keys:", state.keys())
    assert "context" in state
    assert state["context"] == ["some data"]
    assert state["previous_responses"] == ["previous answer"]
    
    print("\n✅ RL State Integration test passed!")
    
except Exception as e:
    print(f"\n❌ RL State Integration test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
