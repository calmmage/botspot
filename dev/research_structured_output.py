# %%
print(1)


# %%
def warn_once():
    if not hasattr(warn_once, "warned"):
        print("warned")
        warn_once.warned = True

    print("main code")


# warn_once.warned = False

warn_once()
warn_once()
warn_once()
# %%
import litellm

# %%
print(1)
# %%
import langchain

# %%
from dotenv import load_dotenv

load_dotenv()
# idea: compare structured output
from typing import Optional

# case 1: all info is present
from pydantic import BaseModel

system_message = (
    "You're unstructured checkin parsing assistant. You goal is to extract information from the user message and output it as a structured object."
    "if some of the mandatory fields are missing, include their names into the missing field as a list"
)

message = """
Hello, this is Dan Pulido, I am writing from Washingtom to check-in.
"""


class CheckInData(BaseModel):
    first_name: str
    last_name: Optional[str]
    location: str


def test(message, Model):
    print("Message:", message)
    # option 1: call calmlib
    from calmlib.utils.llm_utils.gpt_utils import query_llm_structured

    response_1 = query_llm_structured(
        prompt=message,
        model="gpt-4o-mini",
        output_schema=Model,
        system=system_message,
        engine="openai",
    )
    print("response 1:", response_1)
    print()
    # option 2: use litellm
    from litellm import completion

    response_2 = completion(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": message},
        ],
        response_format=Model,
    )
    print("Response 2:", response_2.choices[0].message.content)
    print()
    import json

    item = Model(**json.loads(response_2.choices[0].message.content))
    print("Item:", item)


# %%
test(message, CheckInData)
# %%
message = """
secret password: 2462
"""
from typing import List


class Response(BaseModel):
    secret_password: str
    secret_password_2: str
    secret_password_3: Optional[str]
    missing: List[str]
    extra_mandatory_field: bool
    extra_optional_field: Optional[bool]


test(message, Response)
# %%
response_2.choices[0].message.content
# %%
# so, final - what do I want

# command 1: just ... with structured output
# command 2: handle the 'missing arguments' situation
#  - unprocessed - part of the text that ... llm didn't use for forming a response
#  - missing - mandatory field that doesn't have a value
#  -
