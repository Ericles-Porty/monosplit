# Treatment: the LLM

## Model and profiles

The treatment is a general-purpose large language model (LLM), without fine-tuning or a specialised framework. Each model is described by a profile, stored in the database and edited on the Configuration page, with provider, model, request parameters (for example, the reasoning effort) and prices. The runs of each profile are kept apart in the database, identified by the profile name.

The final experiment used the OpenAI model `gpt-6.1-sol` with `reasoning_effort` high (profile `gpt-6.1-sol-high`), chosen after the pilot runs. The temperature is not sent: the API default applies, and the record of each attempt says so.

The layer `src/monosplit/llm/` defines a common interface and one adapter per provider: OpenAI, Anthropic, Google, servers compatible with the OpenAI API (Application Programming Interface) and Ollama, which runs open-weight models on this machine (section Local models, below). Testing another model needs only a new profile.

The model is a controlled variable. The provider does not switch models automatically, and the model reported by the API is recorded with every attempt.

## Prompt

The prompt `decomposition_base`, stored in the database, was written before the pilot runs, under the name `decomposition_v1`. It sends the full class names and the edge list with call counts, asks for every class in exactly one service, lets the model choose *K* (at least 2) and asks for a single JSON (JavaScript Object Notation) object. The prompt names no metric and no size range, so the treatment is not tuned to the dependent variables.

A prompt version is never overwritten. The Configuration page creates `decomposition_v2`, `decomposition_v3` and so on, and each run records the cryptographic hash of the exact text that was sent.

## Acceptance rule

An answer is accepted when:

1. it contains a JSON object, bare, in a code fence or surrounded by text;
2. the object follows the format `{"microservices": [{"name": "...", "classes": ["..."]}]}`;
3. every class name is one of the classes sent in the prompt;
4. no class appears more than once;
5. every class sent appears;
6. there are at least two non-empty services.

Services without classes are dropped and counted, without rejecting the answer. The first failing check is the rejection reason: `invalid_json`, `invalid_schema`, `unknown_class`, `duplicate_class`, `missing_class` or `too_few_services`; a refusal by the provider is recorded as `refusal`.

## Retries

An invalid output is sent again with the same prompt, without feedback to the model, up to 3 times, which gives up to 4 attempts per run. Every accepted output is therefore a zero-shot sample. A run with 4 invalid attempts is a failed run, and every attempt is counted. API errors, such as network failures or rate limits, are not model outputs: they are logged and stop the run, which continues from where it stopped when started again.

## Variant with obfuscated names

The classes are renamed to C01, C02 and so on, in a seeded random order that does not follow the packages. The edges and the prompt template are the same as in the original variant. The Decompositions page shows the names the model received.

## Records

Every attempt stores the prompt exactly as sent, the raw answer, the model reported by the API, the input and output tokens, the time and the cost computed with the profile's prices. A variant started under one configuration (model, parameters, prompt and graph) refuses to resume under another.

## Local models

An open-weight model was planned as a separate replication, outside the main factor, as the roteiro allows: the same prompt, the same applications and variants and the same acceptance rule, under its own profile. The replication was piloted with gpt-oss:20b and qwen3.5:4b and then dropped: on this machine, with 6 GB of video memory, an attempt took 6 to 57 minutes, and on AcmeAir and DayTrader most answers failed the acceptance rule. The study reports it as a limitation. The tool still runs local models, as described below. The provider `ollama` calls the Ollama server of this machine through its native API. The OpenAI-compatible API that Ollama also offers does not suit the study: it cannot set the context window per request, and the server default (4,096 tokens with less than 24 GB of video memory) silently cuts the larger prompts, such as DayTrader's, with about 10 thousand tokens.

- **Context window.** The profile fixes `options.num_ctx`, sent with every request. The server refuses a prompt that does not fit instead of cutting it, and the tool refuses the configuration when the prompt and the output limit together do not fit in the context. Such a refusal is a configuration error: it stops the run and does not count as an attempt.
- **Seed.** With the same seed and the same prompt, Ollama can return the same answer in every attempt. So each attempt gets its own seed, derived from the master seed, the experiment name, the application, the profile, the variant and the attempt number, and stored with it, so the runs differ from each other. In the tests with two models, repeating an attempt with its seed gave the same answer for one of them. For the other, the part of the prompt the server reuses from its cache between attempts changes at every call, and the answer changes with it.
- **Model identity.** An Ollama tag can be moved to other weights. Each variant stores the digest of the weights, the quantization, the model's default parameters and the server version, and does not resume with other weights. Each attempt stores the server version, the context allocated and the share of the model in GPU memory. Ollama cloud models, which do not run on this machine, are refused.
- **Temperature and reasoning.** Without a temperature in the profile, the model's own default applies, and it is recorded. The reasoning level, when the model has one, goes in the request options (`think`). The reasoning text stays in the raw answer; only the final answer goes through the acceptance rule.
- **Output format.** Ollama's structured output, which restricts generation to a JSON schema, is not used: the treatment is the same prompt sent to the hosted models.
- **Cost.** Nothing is billed. The Execution page starts the run without confirmation and shows the expected time instead of the cost.
