# snomed_translation

This repository contains a proof-of-concept evaluation of using a generative Language Model to translate SNOMED CT from English into a non-English target language.

One of the most resource-intensive tasks that the National Release Centre (NRC) for a non-English speaking SNOMED member country must undertake is to translate the terminology into its native language(s).  Many implementation teams will take advantage of machine-translation capabilities to accelerate the process, however - for a specialist domain like healthcare – machine translations will often be imperfect, necessitating a painstaking human review and correction process.  The size of the SNOMED CT is such that a potentially modest increase in machine translation accuracy could deliver considerable cost savings to members. 

Teams that use machine translation capabilities will likely services like Amazon NMT, Bing NMT, Google NMT or DeepL.  These are “traditional” neural machine-translation (NMT) models (an older architecture when compared to more recently developed decoder-only transformers) and closed source, meaning that end users cannot utilise modern AI implementation techniques to increase task-specific performance. 

Large Language Models (LLMs) offer an alternative to NMT engines for translation use cases.  Furthermore, they offer two potential advantages over using an NMT:

- Firstly, techniques like _Retrieval Augmented Generation_ offer a way to "steer" a translation by providing the model with relevant information that may help to improve translation accuracyy.
- Secondly, _fine-tuning_ offers a mechanism to "teach" an LLM how to conform to the "house style" of a translation team, potentially resulting in translations which require less human correction.

In this repository, we perform a structured comparison of a leading NMT service, [DeepL] (https://www.deepl.com/en/translator), with the open-source, multilingual LLM [Aya-101] (https://cohere.com/research/aya) released by Cohere.

# Method

- We use four target languages for this experiment: Korean, Estonian, Swedish and Dutch.
- Translation accuracy is measured by comparing DeepL / Aya translations to reference translations from the relevant SNOMED CT National Extension.
- We evaluate translation performance using four metrics: Levenshtein Ratio, characTER, Google BLEU and exact matching.
- For Aya, we use three experimental protocols:
    - A "vanilla" translation using a simple prompt.
    - A translation using and "enriched" prompt, in which examples from related concepts (which have target translations already) are retrieved and provided as exemplars.
    - Translations using the "enriched" prompt and following a minimal round of supervised fine-tuning.

# Concept Stratification

The "enriched" prompt relies on the existance of existing translations for "related" concepts.  These can include:

- Defining attributes.
- Parent or "sibling" concepts.
- Lexically similar concepts.

All of which can be combined to provide context for a translation.  Our hypothesis is that richer context will result in more accurate translations.  Therefore, in the `Concept Sampling` notebook we create a set of stratification variables to ensure that we are translating concepts with roughly equal distributions of "contextual richness" from each language.

# Running the notebooks

You will need:

- To install the relevant packages in `requirements.txt`.
- To have an API Key for the DeepL service.
- For the languages you wish to evaluate, a copy of the National Extensions in RF2 format.
- A reference copy of the SNOMED CT International Edition.  The script requires this to be loaded into a graph structure usign the [`snomed_graph`] (https://github.com/VerataiLtd/snomed_graph) library.  (The repo contains instructions on doing this from an RF2 fileset.)
- If fine-tuning, a [Weights & Biases] (https://wandb.ai/) account.

## Working with Aya

Aya-101 is a 13B parameter encoder-decoder model based on the mT5 architecture.  It has been subjected to extensive, multi-lingual instruction-tuning.

The script assumes 24GB of VRAM is available, in which case fine-tuning can be accomplished by loading the model using 4-bit quantization.  There is a toggle in the `translations` script which can be switched to support fine-tuning on AWS SageMaker.  You will need an instance with ~40GB VRAM to fine-tune using fp16 precision.

The script fine-tunes using a LoRA, by default.
