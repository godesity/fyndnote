"""Mock ML backend for text sentiment classification.

POST /inference  {"data": {"text": "..."}}  →  {"annotation": {"sentiment": "positive|negative|neutral"}}
"""

import re
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="mock-ml-backend")


class InferenceRequest(BaseModel):
    data: dict


class InferenceResponse(BaseModel):
    annotation: dict


POSITIVE_WORDS = {
    "good", "great", "excellent", "amazing", "awesome", "fantastic", "wonderful",
    "love", "beautiful", "perfect", "brilliant", "outstanding", "superb",
    "impressive", "masterpiece", "enjoyable", "delightful", "remarkable",
    "best", "fun", "hilarious", "moving", "captivating", "stunning",
}

NEGATIVE_WORDS = {
    "bad", "terrible", "awful", "horrible", "worst", "boring", "dull",
    "disappointing", "poor", "mediocre", "trash", "garbage", "hate",
    "waste", "annoying", "ridiculous", "stupid", "unwatchable", "painful",
    "dreadful", "atrocious", "abysmal", "lame", "pointless",
}


def classify_sentiment(text: str) -> str:
    words = set(re.findall(r"[a-z']+", text.lower()))
    pos_count = len(words & POSITIVE_WORDS)
    neg_count = len(words & NEGATIVE_WORDS)
    if pos_count > neg_count:
        return "positive"
    elif neg_count > pos_count:
        return "negative"
    else:
        return "neutral"


def extract_text(data: dict) -> str:
    for key in ("text", "review", "comment", "sentence", "content", "body"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val
    for val in data.values():
        if isinstance(val, str) and len(val) > 20:
            return val
    return str(next(iter(data.values()), ""))


@app.post("/inference", response_model=InferenceResponse)
def inference(body: InferenceRequest):
    text = extract_text(body.data)
    sentiment = classify_sentiment(text)
    return InferenceResponse(annotation={"sentiment": sentiment})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
