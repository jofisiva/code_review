from local_llm_client import LocalLLMClient

def test_ollama_connection():
    """Test the connection to Ollama with the configured model."""
    print("Testing Ollama connection...")
    
    # Create a client with explicit parameters to ensure we're using the right model
    client = LocalLLMClient(
        api_base_url="http://localhost:11434",
        model_name="llama3.2:1b"
    )
    client.api_type = "ollama"
    
    # Simple prompt to test the model
    prompt = "Write a short function in Python to calculate the factorial of a number."
    
    print(f"Sending prompt to Ollama model '{client.model_name}'...")
    response = client.generate_response(
        prompt=prompt,
        system_message="You are a helpful AI assistant that specializes in writing clean, efficient code.",
        temperature=0.7,
        max_tokens=1000
    )
    
    print("\nResponse from Ollama:")
    print("-" * 50)
    print(response)
    print("-" * 50)
    
    return response

if __name__ == "__main__":
    test_ollama_connection()
