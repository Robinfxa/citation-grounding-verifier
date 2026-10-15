"""A deliberately limited lexical baseline; no benchmark IDs, gold labels or model calls."""

from __future__ import annotations

import re

from grounding.contracts import MAX_CLAIMS, Citation, Claim, VerificationError, VerificationReport

_SPLIT = re.compile(r"(?<=[.!?])\s+|(?<=[。！？])|[\r\n]+")
_WORDS = re.compile(r"[^\W_]+", re.UNICODE)
_NUMBERS = re.compile(r"(?<!\w)[+-]?\d+(?:\.\d+)?(?:%|\b)")
_NEGATION = re.compile(r"\b(?:not|no|never|cannot|without|\w+n't)\b", re.I)
_QUALIFIERS = {"if", "unless", "when", "only", "may", "might", "except"}
_STOP = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "do", "does", "did", "has", "have", "had", "of", "to", "in", "on", "at",
    "not", "no", "never", "cannot", "without",
}
_NONFACT = re.compile(
    r"^(?:thanks(?: you)?|thank you|hello|hi|great|okay|ok|goodbye)[.! ]*$", re.I
)


def sentences(text: str) -> list[str]:
    return [part.strip() for part in _SPLIT.split(text) if part.strip()]


def extract_claims(answer: str) -> list[str]:
    claims = [
        sentence for sentence in sentences(answer)
        if not _NONFACT.fullmatch(sentence)
        and not sentence.endswith(("?", "？"))
        and not sentence.lower().startswith(("please ", "let's "))
    ]
    if len(claims) > MAX_CLAIMS:
        raise VerificationError("invalid_model_output")
    return claims


def _terms(text: str) -> set[str]:
    words = _WORDS.findall(_NUMBERS.sub(" ", _NEGATION.sub(" ", text.lower())))
    return {word[:-1] if len(word) > 3 and word.endswith("s") else word
            for word in words if word not in _STOP}


def judge(passages: list[str], claims: list[str]) -> VerificationReport:
    sources = [(i, s) for i, p in enumerate(passages) for s in sentences(p)]
    results = []
    for claim in claims:
        supporting, refuting = [], []
        terms = _terms(claim)
        numbers = _NUMBERS.findall(claim)
        negative = bool(_NEGATION.search(claim))
        claim_words = set(_WORDS.findall(claim.lower()))
        for index, sentence in sources:
            source_terms = _terms(sentence)
            if not terms or terms != source_terms:
                continue
            if (_QUALIFIERS & set(_WORDS.findall(sentence.lower()))) - claim_words:
                continue
            source_numbers = _NUMBERS.findall(sentence)
            same_negation = negative == bool(_NEGATION.search(sentence))
            if numbers == source_numbers:
                (supporting if same_negation else refuting).append(Citation(index=index, quote=sentence))
            elif same_negation and len(numbers) == len(source_numbers) == 1:
                # AIDEV-NOTE: numeric matching is only a baseline signal, not an NLI proof.
                # Different version/date scopes are not direct numeric refutations.
                if not {"version", "release", "revision", "since", "until"} & claim_words:
                    refuting.append(Citation(index=index, quote=sentence))
        if supporting and refuting:
            verdict, citations = "UNSUPPORTED", []
            reason = "Lexically comparable passages conflict; this baseline cannot resolve them."
        elif supporting:
            verdict, citations = "SUPPORTED", supporting[:1]
            reason = "The sentence matches lexical terms, numbers and negation (heuristic only)."
        elif refuting:
            verdict, citations = "CONTRADICTED", refuting[:1]
            reason = "A comparable sentence differs in negation or one number (heuristic only)."
        else:
            verdict, citations = "UNSUPPORTED", []
            reason = "This conservative lexical baseline found no sufficient matching evidence."
        results.append(Claim(claim_text=claim, verdict=verdict, reasoning=reason, citations=citations))
    return VerificationReport(claims=results)
