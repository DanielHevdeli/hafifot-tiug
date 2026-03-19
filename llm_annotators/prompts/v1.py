from ..config import LABELS

labels = list(LABELS.keys())

prompt = f"You are getting a batch of articles, \
    and you need to annotate each one of them with a specific label, \
        either {', '.join(labels[:-1])} or {labels[-1]}."
