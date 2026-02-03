"""
Run a single query using RetrieverAgent with formatted logs.
"""

import logging

logger = logging.getLogger(__name__)

def run_query(
    retriever_agent,
    query: str,
    db_name: str,
    collection_name: str,
    student_profile: dict = None
):
    """
    Execute a single query using the RetrieverAgent and print formatted logs.
    Returns: {"response": str, "quality_scores": dict} or None on error.
    """
    print("=" * 60)
    print("🔍 Running single query")
    print("=" * 60)

    try:
        result = retriever_agent.orchestrate_retrieval_and_response(
            query=query,
            db_name=db_name,
            collection_name=collection_name,
            student_profile=student_profile
        )

        response = result.get("response", result) if isinstance(result, dict) else result
        quality_scores = result.get("quality_scores", {}) if isinstance(result, dict) else {}

        print("\n" + "-" * 60)
        logger.info("✅ Response generated successfully")
        print("📝 LLM Response:")
        print("-" * 60)
        print(response)
        if quality_scores:
            print("-" * 60)
            print("📊 Quality Score Analysis:")
            for k, v in quality_scores.items():
                print(f"   {k}: {v}%")
        print("-" * 60)

        return result

    except Exception as e:
        logger.error(f"❌ Error during retrieval: {e}")
        print(f"❌ Error during retrieval: {e}")
        return None
