import os
import asyncio
import json

from app.core.ai_engine import AIEngine

async def main():
    provider = os.environ.get('AI_PROVIDER', 'groq')
    api_key = os.environ.get('GROQ_API_KEY', os.environ.get('AI_API_KEY', ''))
    model = os.environ.get('AI_MODEL', '')
    host = os.environ.get('AI_HOST', '')

    print(f"Testing AI provider={provider} model={model} host={host} (api_key present={bool(api_key)})")
    res = await AIEngine.test_connection(provider=provider, api_key=api_key, model=model, host=host)
    print('Connection result:')
    print(json.dumps(res, indent=2))

    if res.get('success'):
        # optional quick LLM query
        test_prompt = os.environ.get('GROQ_TEST_PROMPT')
        if test_prompt:
            print('\nRunning quick query...')
            out = await AIEngine.query_llm(provider=provider, api_key=api_key, model=model, host=host,
                                           system_prompt='You are a test agent. Reply OK.', user_prompt=test_prompt)
            print('Query output:')
            print(out)

if __name__ == '__main__':
    asyncio.run(main())
