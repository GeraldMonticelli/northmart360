from openai import OpenAI

client = OpenAI()

response = client.responses.create(
    model="gpt-5.6",
    input="Réponds uniquement par : connexion LLM OK"
)

print(response.output_text)
