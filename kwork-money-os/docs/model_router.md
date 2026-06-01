# Model Router

Use small/fast models for cheap mechanical tasks and stronger models for judgment.

| Task | Model class | Notes |
| --- | --- | --- |
| fast scan | fast inexpensive model | Summarize local JSON, extract repeated terms. |
| market research | reasoning model | Compare demand, competition, risk, and skill fit. |
| offer writing | strong writing model | Keep concrete scope and avoid risky claims. |
| profile editing | strong writing model | Conservative tone, no fake authority. |
| banner prompting | visual/prompt-writing model | Produce 660x440 prompts and negative prompts. |
| coding | coding model | Edit scripts, selectors, browser flows. |
| final audit | strongest reasoning/coding model | Check policy, security, and live-action gates. |

Default route:
- use fast scan for `data/market/*.json` cleanup;
- use reasoning for opportunity scoring and final decisions;
- use coding model for browser bridge changes;
- use final audit before any live profile/draft operation.
