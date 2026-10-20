# Benchmark dataset process

The committed dataset is synthetic and offline. A future Live target is 50 manually
reviewed Shopee URLs plus 50 manually reviewed Lazada URLs, only after the operator has
confirmed lawful access. Each row must store the URL, platform, collection timestamp,
annotator, exact product/variant/offer fields, evidence excerpt/hash, and access status.

“Target URL” is not counted as fetched. Reports must retain attempted/allowed/fetched/
restricted denominators, dataset version, environment, latency, missingness and cost.
Manual relevance labels are required for Precision@K/NDCG@K. LLM-generated answers may
not be used as their own ground truth. Live smoke is separately opt-in and is `N/A` here.
