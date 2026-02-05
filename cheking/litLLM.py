from litellm import completion
import json
response = completion(
    model="groq/llama-3.3-70b-versatile",
    messages=[
        {"role": "user", "content": "Explain Groq in one sentence"}
    ]
)
# print(json.dumps(response, indent=4))
print(json.dumps(response.model_dump(), indent=4))

# print(response.choices[0].message.content)
