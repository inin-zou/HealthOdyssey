import os
from mistralai import Mistral
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

# Set up Mistral API client
client = Mistral(api_key=MISTRAL_API_KEY)
model = "mistral-large-latest"

def chat_with_mistral(user_input: str) -> str:
    """Send a request to Mistral AI's API and return the response."""
    try:
        response = client.chat.complete(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful AI assistant."},
                {"role": "user", "content": user_input},
            ],
            tool_choice="any",
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit"]:
            print("Exiting chatbot...")
            break
        response = chat_with_mistral(user_input)
        print("Bot:", response)
