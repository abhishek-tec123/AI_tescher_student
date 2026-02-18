import os
import sys
import logging
from unittest.mock import MagicMock

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

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
    
    print("Testing diagnosis_chat with RL integration...")
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
    
    print("\nTesting reward calculation...")
    optimizer = RLOptimizer()
    reward = optimizer.calculate_reward("like", result["quality_scores"])
    print(f"Reward for 'like': {reward}")
    
    reward_dislike = optimizer.calculate_reward("dislike", result["quality_scores"])
    print(f"Reward for 'dislike': {reward_dislike}")
    
    print("\n✅ RL Integration test passed!")
    
except Exception as e:
    print(f"\n❌ RL Integration test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
