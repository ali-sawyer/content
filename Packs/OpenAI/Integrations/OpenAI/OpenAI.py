import demistomock as demisto  # noqa: F401
from CommonServerPython import *  # noqa: F401






import json
import urllib3

urllib3.disable_warnings()

PREFIX = "openai"  # prefix at front of all commands
CHAT_DEFAULT_MODEL = "gpt-3.5-turbo"
COMPLETIONS_DEFAULT_MODEL = "gpt-3.5-turbo-instruct"


''' CLIENT CLASS '''


class Client(BaseClient):
    """
        Client class to interact with the OpenAI and Azure OpenAI APIs
    """
    def __init__(self, api_key: str, base_url: str, proxy: bool, is_azure: bool, verify: bool, version: str):
        super().__init__(base_url=base_url, proxy=proxy, verify=verify)
        self.api_key = api_key
        self.base_url = base_url
        self.is_azure = is_azure
        self.version = version
        self.headers = {"Content-Type": "application/json"}
        if self.is_azure:  # Azure OpenAI
            self.headers["api-key"] = self.api_key
        else:  # standard api.openai.com
            self.headers["Authorization"] = f"Bearer {self.api_key}"

    def completions(self, prompt: str, model: str = COMPLETIONS_DEFAULT_MODEL, temperature: float = 0.7,
                    max_tokens: int = 256, top_p: float = 1, frequency_penalty: int = 0,
                    presence_penalty: int = 0, best_of: int = 1, stop: str = None) -> dict:
        """
            Enter an instruction and watch the OpenAI API respond with a completion that attempts to match the context
            or pattern you provided, using the 'completions' endpoint.

            :type prompt: ``str``
            :param prompt: Instruction
            :type model: ``str``
            :param model: The model which will generate the completion.
            :type temperature: ``float``
            :param temperature: Controls randomness: Lowering results in less random completions.
            :type max_tokens: ``int``
            :param max_tokens: The maximum number of tokens to generate.
            :type top_p: ``float``
            :param top_p: Controls Diversity via nucleus sampling
            :type frequency_penalty: ``int``
            :param frequency_penalty: How much to penalize new tokens based on their existing frequency in the text so far.
            :type presence_penalty: ``int``
            :param presence_penalty: How much to penalize new tokens based on whether they appear in the text so far.
            :type best_of: ``int``
            :param best_of: Generates best_of completions server-side and returns the "best"
            :type stop: ``str``
            :param stop: The returned text won't contain the stop sequence.

            :return: response of the OpenAI Completion API
            :rtype: ``dict``
        """

        # available API params for OpenAI: https://platform.openai.com/docs/api-reference/completions/create
        # available API params for Azure OpenAI: https://learn.microsoft.com/en-us/azure/cognitive-services/openai/reference#completions
        data = {
            "prompt": prompt,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "frequency_penalty": frequency_penalty,
            "presence_penalty": presence_penalty,
            "best_of": best_of,
            "stop": stop
        }
        if self.is_azure:  # Azure OpenAI
            url_suffix = f"openai/deployments/{model}/completions?api-version={self.version}"
        else:  # standard api.openai.com
            data["model"] = model
            url_suffix = "v1/completions"
        return self._http_request(
            method='POST', url_suffix=url_suffix, json_data=data,
            headers=self.headers, resp_type='json', ok_codes=(200,)
        )

    def chatgpt(self, prompt: str, model: str = CHAT_DEFAULT_MODEL) -> dict:
        """
            Send prompt to ChatGPT using the 'chat/completions' endpoint.

            Args:
                prompt (str): Input to ChatGPT
                model (str): The model which will generate the chat response

            Returns:
                dict: HTTP response from the OpenAI Chat API
        """
        options = {
            "max_tokens": 1000,
            "messages": [{
                "role": "user",
                "content": prompt
            }]
        }
        if self.is_azure:  # Azure OpenAI
            url_suffix = f"openai/deployments/{model}/chat/completions?api-version={self.version}"
        else:  # standard api.openai.com
            options["model"] = model
            url_suffix = "v1/chat/completions"
        return self._http_request(
            method='POST', url_suffix=url_suffix,
            json_data=options, headers=self.headers,
            resp_type="json", ok_codes=(200,)
        )


''' HELPER FUNCTIONS '''


def chatgpt_output(response) -> CommandResults:
    """
        Convert response from ChatGPT to a human readable format in markdown table

        :return: CommandResults return output of ChatGPT response
        :rtype: ``CommandResults``
    """
    if response and isinstance(response, dict):
        rep = json.dumps(response)
        repJSON = json.loads(rep)
        model = repJSON.get('model')
        createdTime = repJSON.get('created')
        id = repJSON.get('id')
        choices = repJSON.get('choices', [])[0].get('message', {}).get('content', "").strip('\n')
        promptTokens = repJSON.get('usage', {}).get('prompt_tokens')
        completionTokens = repJSON.get('usage', {}).get('completion_tokens')
        totalTokens = repJSON.get('usage', {}).get('total_tokens')
        context = [{'id': id, 'Model': model,
                    'ChatGPT Response': choices, 'Created Time': createdTime,
                    'Number of Prompt Tokens': promptTokens,
                    'Number of Completion Tokens': completionTokens,
                    'Number of Total Tokens': totalTokens
                    }]

        markdown = tableToMarkdown(
            'ChatGPT API Response',
            context,
            date_fields=['Created Time'],
        )
        results = CommandResults(
            readable_output=markdown,
            outputs_prefix='OpenAI.ChatGPTResponse',
            outputs_key_field='id',
            outputs=context
        )
        return results
    else:
        raise DemistoException('Error in results')


''' COMMAND FUNCTIONS '''


def test_module(client: Client, model: str) -> str:
    """
        Tests OpenAI API connectivity and authentication
    """
    test_prompt = "Can I connect to OpenAI?"
    if model:
        result = client.chatgpt(prompt=test_prompt, model=model)
    else:
        result = client.chatgpt(prompt=test_prompt)
    if result:
        return 'ok'
    else:
        return 'Did not receive a response from OpenAI API'


def chatgpt_send_prompt_command(client: Client, prompt: str,
                                model: str = CHAT_DEFAULT_MODEL) -> CommandResults:
    """
        Command to send prompts to OpenAI ChatGPT API
        and receive a response converted into json then
        returned to Output function to convert it to markdown table

        :type client: ``Client``
        :param prompt:  arguments
    """
    if not prompt:
        raise DemistoException('the prompt argument cannot be empty.')

    chatgpt_response = client.chatgpt(prompt, model=model)
    return chatgpt_output(chatgpt_response)


def completions_command(client: Client, args: dict) -> CommandResults:
    """
        Enter an instruction and watch the OpenAI API respond with a completion that attempts to match the context
        or pattern you provided, using the 'completions' endpoint.

        :type client: ``Client``
        :param client: instance of Client class to interact with OpenAI API
        :type args: ``dict``
        :param args:  arguments

        :return: CommandResults instance of the OpenAI Completion API response
        :rtype: ``CommandResults``
    """
    prompt = args.get('prompt', False)

    if not prompt:
        raise ValueError('No prompt argument was provided')

    model = args.get('model', COMPLETIONS_DEFAULT_MODEL)
    temperature = args.get('temperature', 0.7)
    max_tokens = args.get('max_tokens', 256)
    top_p = args.get('top_p', 1)
    frequency_penalty = args.get('frequency_penalty',0)
    presence_penalty = args.get('presence_penalty', 0)
    best_of = args.get("best_of", 1)
    stop = args.get("stop", None)

    response = client.completions(
        prompt=prompt, model=model, temperature=float(temperature),
        max_tokens=int(max_tokens), top_p=int(top_p),
        frequency_penalty=int(frequency_penalty), presence_penalty=int(presence_penalty),
        best_of=int(best_of), stop=stop
    )
    meta = None
    context = None

    if response and isinstance(response, dict):
        model = response.get('model')
        id = response.get('id')
        choices = response.get('choices', [])
        meta = f"Model {response.get('model')} generated {len(choices)} possible text completion(s)."
        context = [{'id': id, 'model': model, 'text': choice.get('text')} for choice in choices]

    return CommandResults(
        readable_output=tableToMarkdown('OpenAI - Completions', context, metadata=meta, removeNull=True),
        outputs_prefix='OpenAI.Completions',
        outputs_key_field='id',
        outputs=context,
        raw_response=response
    )


''' MAIN FUNCTION '''


def main() -> None:
    """main function, runs command functions
    """
    params = demisto.params()
    args = demisto.args()
    command = demisto.command()

    api_key = params.get('apikey')
    base_url = params.get('url', '')
    if base_url[-1] != '/':
        base_url = base_url + '/'
    is_azure = params.get('is_azure', False)
    verify = not params.get('insecure', False)
    proxy = params.get('proxy', False)
    version = params.get('version', '2023-03-15-preview')
    test_model = params.get('test_model', '')

    # set env variable for API key
    os.environ["OPENAI_API_KEY"] = api_key
    # set additional required env variables for Azure OpenAI
    if is_azure:
        os.environ["OPENAI_API_TYPE"] = "azure"
        os.environ["OPENAI_API_VERSION"] = version
        os.environ["OPENAI_API_BASE"] = base_url

    demisto.debug(f'Command being called is {command}')
    try:
        client = Client(api_key=api_key, base_url=base_url, is_azure=is_azure, verify=verify, proxy=proxy, version=version)

        if command == 'test-module':
            # This is the call made when clicking the integration Test button.
            return_results(test_module(client, test_model))

        elif command == f'{PREFIX}-chatgpt':
            return_results(chatgpt_send_prompt_command(client, **args))

        elif command == f'{PREFIX}-completions':
            return_results(completions_command(client=client, args=args))

        else:
            raise NotImplementedError(f"command {command} is not implemented.")

    # Log exceptions and return errors
    except Exception as e:
        demisto.error(traceback.format_exc())  # print the traceback
        return_error("\n".join((f"Failed to execute {command} command.",
                                 "Error:", str(e))))


''' ENTRY POINT '''


if __name__ in ('__main__', '__builtin__', 'builtins'):
    main()


