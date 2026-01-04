from prometheus_client import Counter

_shared_labelnames = (
    "type",  # type is one of "submission", "comment", or "mention"
    "subreddit",  # you'd probably have to really try to make this high-cardinality
)

responses_counter = Counter(
    "crom_reddit_responses_total",
    "crom_reddit_responses_total",
    labelnames=_shared_labelnames,
)
