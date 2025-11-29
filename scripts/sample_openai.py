import mimetypes
from pathlib import Path

from dotenv import load_dotenv
import os
import openai
from openai.types.chat import ChatCompletionUserMessageParam, ChatCompletionContentPartInputAudioParam
from openai.types.chat.chat_completion_content_part_input_audio_param import InputAudio
from openai.types.responses import EasyInputMessageParam, ResponseInputAudioParam, ResponseInputFileParam, \
    ResponseInputTextParam, FunctionToolParam

import config

load_dotenv()

client = openai.OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    # base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    base_url="https://aipipe.org/openrouter/v1/"
)


def sample_conversation_api():
    # Note: The Conversations API is currently not working with aipipe
    # Response: "openai.BadRequestError: Error code: 400 - {'message': 'Model undefined pricing unknown'}"
    # conversation = openai.conversations.create()
    conversation = openai.conversations.create(
        model="gpt-5-nano",
        items=[{"role": "user", "content": "what are the 5 Ds of dodgeball?"}],
        metadata={"user_id": "peter_le_fleur"},
    )
    response = openai.responses.create(
        model="gpt-5-nano",
        input=[
            {"role": "user", "content": "What are the 5 Ds of dodgeball?"}
        ],
        conversation=conversation.id
    )

    print("Response:", response)


def sample_conversation_style_branching_using_response_api():
    start_token = 0
    response = client.responses.create(
        model="gpt-4o-mini",
        input=[EasyInputMessageParam(role="system",
                                     content="You are a helpful assistant list my expenses. only provide item then (count*rate)=total then finally all over total")]
    )
    print(response.output_text, response.usage)
    start_token = response.usage.total_tokens
    total_tokens = start_token
    print('-' * 50)
    FunctionToolParam
    branch_1_total_tokens = start_token
    branch_1_response = client.responses.create(
        model="gpt-4o-mini",
        previous_response_id=response.id,
        input=[EasyInputMessageParam(role="user", content="banana 10 rate 5, apple 5 rate 10, orange 8 rate 7")],
        tools=[
            {"name": "expense_calculator",
             "type": "function",
             # "function": {
             # "name": "expense_calculator",
             "description": "Calculates total expenses based on item counts and rates.",
             "parameters": {
                 "type": "object",
                 "properties": {
                     "items": {
                         "type": "array",
                         "items": {
                             "type": "object",
                             "properties": {
                                 "item_name": {"type": "string"},
                                 "count": {"type": "number"},
                                 "rate": {"type": "number"}
                             },
                             "required": ["item_name", "count", "rate"]
                         }
                     }
                 },
                 "required": ["items"]
             },
             # }
             }
        ],
        tool_choice="required"
    )
    print(branch_1_response.output_text, response.usage)
    total_tokens += response.usage.total_tokens
    branch_1_total_tokens += response.usage.total_tokens
    print('-' * 50)

    branch_1_response_cont = client.responses.create(
        model="gpt-4o-mini",
        previous_response_id=branch_1_response.id,
        input=[EasyInputMessageParam(role="user", content="pear 12 rate 11, pineapple 25 rate 15")],
        # input=[{"role": "user", "content": "mango 15 rate 12, grapes 20 rate 9"}],
    )
    print(branch_1_response_cont.output_text, response.usage)
    total_tokens += response.usage.total_tokens
    branch_1_total_tokens += response.usage.total_tokens
    print('-' * 50)

    print("Total tokens used in branch 1:", branch_1_total_tokens)

    branch_2_total_tokens = response.usage.total_tokens
    branch_2_response = client.responses.create(
        model="gpt-4o-mini",
        previous_response_id=response.id,
        input=[EasyInputMessageParam(role="user", content="car 10000 rate 8, bike 5000 rate 6")],
        # input=[{"role": "user", "content": "car 10000 rate 8, bike 5000 rate 6"}],
    )
    print(branch_2_response.output_text, response.usage)
    total_tokens += response.usage.total_tokens
    branch_2_total_tokens += response.usage.total_tokens
    print('-' * 50)

    branch_2_response_cont = client.responses.create(
        model="gpt-4o-mini",
        previous_response_id=branch_2_response.id,
        input=[EasyInputMessageParam(role="user", content="bus 30000 rate 7, train 20000 rate 5")],
        # input=[{"role": "user", "content": "bus 30000 rate 7, train 20000 rate 5"}],
    )
    print(branch_2_response_cont.output_text, response.usage)
    total_tokens += response.usage.total_tokens
    branch_2_total_tokens += response.usage.total_tokens
    print('-' * 50)
    print("Total tokens used in branch 2:", branch_2_total_tokens)

    print("Total tokens used in conversation style branching:", total_tokens)


def array_style_keep_context_using_response_api():
    # as same as above but using array style input to keep context
    branch_1_response = client.responses.create(
        model="gpt-4o-mini",
        input=[
            EasyInputMessageParam(role="system",
                                  content="You are a helpful assistant list my expenses. only provide item then (count*rate)=total then finally all over total"),
            EasyInputMessageParam(role="user", content="banana 10 rate 5, apple 5 rate 10, orange 8 rate 7"),
            EasyInputMessageParam(role="user", content="pear 12 rate 11, pineapple 25 rate 15"),
        ],
    )
    print(branch_1_response.output_text, branch_1_response.usage)
    print('-' * 50)

    branch_2_response = client.responses.create(
        model="gpt-4o-mini",
        input=[
            EasyInputMessageParam(role="system",
                                  content="You are a helpful assistant list my expenses. only provide item then (count*rate)=total then finally all over total"),
            EasyInputMessageParam(role="user", content="car 10000 rate 8, bike 5000 rate 6"),
            EasyInputMessageParam(role="user", content="bus 30000 rate 7, train 20000 rate 5"),
        ],
    )
    print(branch_2_response.output_text, branch_2_response.usage)
    print('-' * 50)

    print("Total tokens used in array style context keeping:",
          branch_1_response.usage.total_tokens + branch_2_response.usage.total_tokens)


def get_file_data(resource_file: str) -> str:
    import base64
    data = Path(config.project_path / "resources" / resource_file).read_bytes()
    # as data url: ex: data:image/png;base64,
    mime_type, _ = mimetypes.guess_type(resource_file)
    if not mime_type:
        mime_type = "application/octet-stream"
    elif mime_type == "application/ogg":
        mime_type = "audio/wav"
    print("mime_type:", mime_type)
    return f"data:{mime_type};base64,{base64.b64encode(data)}"
    # return base64.b64encode(data).decode('utf-8')


def sample_files_analysis_openai():
    # response = client.responses.create(
    #     model="gpt-4o-mini-audio-preview",
    #     input=[
    #         EasyInputMessageParam(
    #             role="user",
    #             content=[
    #                 {
    #                     "type": "input_file",
    #                     "file_url": "https://tds-llm-analysis.s-anand.net/demo-audio.ogx",
    # "file_data": get_file_data("samples/demo-audio.ogx"),
    # },
    # {
    #     "type": "input_file",
    #     # "file_url": "https://tds-llm-analysis.s-anand.net/demo-audio-data.csv",
    #     "file_data": get_file_data("samples/demo-audio-data.csv"),
    # },
    # {
    #     "type": "input_text",
    #     "text": "Analyze the audio file and provide insights based on the data in the CSV file.",
    # }
    # ResponseInputFileParam(
    #     type="input_file",
    #     # file_url="https://tds-llm-analysis.s-anand.net/demo-audio.opus",
    #     file_data=get_file_data("samples/demo-audio.ogx"),
    #     file_name="demo-audio.ogx"
    # ),
    # ResponseInputFileParam(
    #     type="input_file",
    #     # file_url="https://tds-llm-analysis.s-anand.net/demo-audio-data.csv",
    #     file_data=get_file_data("samples/demo-audio-data.csv")
    # ),
    # ResponseInputTextParam(
    #     type="input_text",
    #     text="Analyze the audio file and provide insights based on the data in the CSV file.",
    # )
    # ]
    # )
    # ]
    # )
    response = client.chat.completions.create(
        model="gpt-4o-mini-audio-preview",
        messages=[
            # ChatCompletionUserMessageParam(
            #     role="user",
            #     content=[
            #         ChatCompletionContentPartInputAudioParam(
            #             type="input_audio",
            #             input_audio=InputAudio(
            #                 data=get_file_data("samples/demo-audio.ogx"),
            #                 format="wav"
            #             )
            #         )
            {"role": "user",
             "content": [{
                 "type": "input_audio",
                 "input_audio": {
                     "data": get_file_data("samples/demo-audio.ogx"),
                     "format": "wav"
                 }
             }]}
            # {
            #     "type": "input_file",
            #     "file_data": get_file_data("samples/demo-audio-data.csv"),
            # },
            # {
            #     "type": "input_text",
            #     "text": "Analyze the audio file and provide insights based on the data in the CSV file.",
            # }

            # ]
            # )
        ]
    )
    print("Response:", response.output_text)
    print("Usage:", response.usage)


def sample_audio_file_as_base64_text_openai():
    response = client.responses.create(
        model="anthropic/claude-3-sonnet-20240229",
        input=[
            EasyInputMessageParam(
                role="user",
                content=[
                    {
                        "type": "input_file",
                        "input_file": get_file_data("samples/demo-audio.ogx")
                    }
                    # ResponseInputAudioParam(
                    #     type="input_audio",
                    #     # file_url="https://tds-llm-analysis.s-anand.net/demo-audio.opus",
                    #     file_data=get_file_data("samples/demo-audio.ogx"),
                    #     filename="demo-audio.ogx"
                    # ),
                    # ResponseInputTextParam(
                    #     type="input_text",
                    #     text="Provide a summary of the audio content." + get_file_data("samples/demo-audio.ogx")
                    # )
                ]
            )
        ]
    )
    print("Response:", response)
    print("Usage:", response.usage)


def sample_openai_transcription_api():
    file_path = config.project_path / "resources" / "samples" / "demo-audio.ogx"
    with open(file_path, "rb") as f:
        file = f.read()
    transcription = client.audio.transcriptions.create(
        model="gpt-4o-transcribe",
        file=file,
        response_format="text",
        prompt="The following conversation is a lecture about the recent developments around OpenAI, GPT-4.5 and the future of AI."
    )
    print("Transcription:", transcription)


if __name__ == "__main__":
    """
    Reference: https://platform.openai.com/docs/guides/conversation-state#passing-context-from-the-previous-response
    Response objects are saved for 30 days by default.
    """
    ## Note: Total tokens used in array style context keeping: 343
    # array_style_keep_context_using_response_api()
    ## Note: Total tokens used in conversation style branching: 290
    # sample_conversation_style_branching_using_response_api()
    ## Note: The Conversations API is currently not working with aipipe
    sample_conversation_api()
    # Note: only supported type can be sent as file input
    # Refer: https://platform.openai.com/docs/assistants/tools/file-search#supported-files
    # sample_files_analysis_openai()
    # Note: got response as instruction to transcribe the audio, check in the chatgpt also it gave the kind of response
    # sample_audio_file_as_base64_text_openai()
    # Note: openai.BadRequestError: Error code: 400 - {'message': 'Pass a JSON body with {model} so we can calculate cost'}
    # sample_openai_transcription_api()
    # sample_openai_transcription_with_chat_completion_api()
