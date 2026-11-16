# calling through LLM
from llm import agent

def user_response_from_llm(user_id: str, user_message : str) :
    input_data = {"messages": [{"role": "user", "content": user_message}]}
    config = {"configurable": {"thread_id": user_id}}

    print(input_data)

    result = agent.invoke(input_data, config)
    last_message = result['messages'][-1]

    # print(result)
    # print(last_message.content)

    return str(last_message.content)